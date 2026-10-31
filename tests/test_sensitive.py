"""End-to-end gate tests using only independent temporary Git repositories."""

from __future__ import annotations

import os
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCANNER = Path(__file__).resolve().parents[1] / "scripts" / "check_sensitive.py"


@unittest.skipUnless(shutil.which("git"), "Git is required")
class SensitiveIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="neurocore-sensitive-")
        self.addCleanup(self.cleanup_temporary)
        self.repo = Path(self.temporary.name)
        # Scope ownership permission to this disposable repository; never alter global config.
        self.environment = os.environ.copy()
        self.environment.update(
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
            GIT_CONFIG_VALUE_0=str(self.repo),
        )
        self.git("init", "--quiet")

    def git(self, *args: str, data: bytes | None = None) -> bytes:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo), *args], input=data, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=self.environment, check=False,
            )
        except (OSError, ValueError):
            raise AssertionError("Synthetic Git fixture operation failed") from None
        if result.returncode:
            raise AssertionError("Synthetic Git fixture operation failed")
        return result.stdout

    def cleanup_temporary(self) -> None:
        try:
            self.temporary.cleanup()
        except OSError:
            raise AssertionError("Synthetic fixture cleanup failed") from None

    def stage(self, name: str, content: str | bytes) -> None:
        try:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        except (OSError, ValueError):
            raise AssertionError("Synthetic file fixture creation failed") from None
        self.git("add", "--force", "--", name)

    def check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCANNER), "--repo", str(self.repo)],
            capture_output=True, text=True, encoding="utf-8", env=self.environment,
            check=False,
        )

    def assert_rejected(self, result: subprocess.CompletedProcess[str], rule: str) -> None:
        self.assertEqual(result.returncode, 1, "Expected a finding exit code")
        self.assertTrue(rule in result.stderr, "Expected diagnostic category missing")
        self.assertTrue("passed" not in result.stdout, "Rejected input reported success")

    def assert_redacted(self, result: subprocess.CompletedProcess[str], *values: str) -> None:
        self.assertTrue(
            all(value not in result.stdout and value not in result.stderr for value in values),
            "Diagnostic output exposed a sensitive fixture",
        )

    def synthetic_token(self) -> str:
        return "gh" + "p_" + "SYNTHETIC" + secrets.token_hex(18)

    def assert_indexed(self, names: list[str], body: bytes) -> list[bytes]:
        indexed = [name for name in self.git("ls-files", "-z").split(b"\0") if name]
        self.assertTrue(set(indexed) == {name.encode("utf-8") for name in names},
                        "Expected fixture paths are not the complete index")
        for name in names:
            self.assertTrue(self.git("show", ":" + name) == body, "Unexpected indexed fixture body")
        return indexed

    def test_clean_source_docs_and_lock_hashes_pass(self) -> None:
        self.stage("src/neurocore/example.py", 'print("hello")\n')
        self.stage("src/neurocore/models/__init__.py", '"""Public data models."""\n')
        self.stage("docs/guide.md", "# Public guide\n中文文档。\n")
        self.stage("uv.lock", 'version = 1\nhash = "sha256:' + "a0" * 32 + '"\n')
        result = self.check()
        self.assertEqual(result.returncode, 0, "Clean source rejected")
        self.assertTrue("all Git-index entries checked" in result.stdout, "Success category missing")

    def test_empty_index_is_clean(self) -> None:
        self.assertEqual(self.check().returncode, 0)

    def test_known_credentials_are_detected_without_values(self) -> None:
        examples = (
            ("aws-access-key", "AK" + "IA" + "A" * 16),
            ("github-token", "gh" + "p_" + "a" * 36),
            ("slack-token", "xo" + "xb-" + "1" * 12 + "-" + "a" * 24),
            ("google-api-key", "AI" + "za" + "a" * 35),
            ("service-secret-key", "s" + "k-proj-" + "a" * 40),
            ("jwt", "ey" + "J" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12),
            ("url-credentials", "https://" + "synthetic-user:" + "synthetic-pass" + "@example.invalid/"),
        )
        for index, (_, value) in enumerate(examples):
            self.stage(f"sample_{index}.txt", value)
        result = self.check()
        for rule, value in examples:
            with self.subTest(rule=rule):
                self.assert_rejected(result, rule)
                self.assert_redacted(result, value)

    def test_private_key_headers_are_detected(self) -> None:
        for index, kind in enumerate(("", "RSA ", "EC ", "OPENSSH ", "ENCRYPTED ")):
            value = "-----BE" + "GIN " + kind + "PRIVATE " + "KEY-----"
            self.stage(f"key_header_{index}.txt", value)
        result = self.check()
        self.assert_rejected(result, "private-key")
        self.assertEqual(result.stderr.count(": private-key"), 5)
        self.assert_redacted(result, "-----BEGIN")

    def test_generic_assignments_are_detected(self) -> None:
        examples = (
            ("API" + "_KEY", " = ", '"'),
            ("SERVICE" + "_TOKEN", "=", ""),
            ('"' + "pass" + "word" + '"', ": ", '"'),
            ("client" + "Secret", ": ", "'"),
            ("access" + "_key_id", ": ", ""),
        )
        value = "synthetic" + "-hardcoded-value"
        for index, (name, separator, quote) in enumerate(examples):
            self.stage(f"assignment_{index}.txt", name + separator + quote + value + quote)
        result = self.check()
        self.assert_rejected(result, "credential-assignment")
        self.assertEqual(result.stderr.count(": credential-assignment"), len(examples))
        self.assert_redacted(result, value)

    def test_placeholders_and_runtime_environment_references_pass(self) -> None:
        name = "API" + "_KEY"
        values = (
            '""', '"REPLACE_ME"', '"<PROVIDER_KEY>"', '"${PROVIDER_KEY}"',
            "None", 'os.environ["PROVIDER_KEY"]', 'os.getenv("PROVIDER_KEY")',
            "process.env.PROVIDER_KEY",
        )
        self.stage("examples.txt", "\n".join(name + " = " + value for value in values))
        result = self.check()
        self.assertEqual(result.returncode, 0, "Safe placeholders rejected")

    def test_force_tracked_env_is_rejected(self) -> None:
        self.stage(".gitignore", ".env\n")
        self.stage(".env", "PUBLIC_SETTING=hello\n")
        self.assert_rejected(self.check(), "denied-filename")

    def test_denied_directories_and_filenames_at_any_depth(self) -> None:
        names = (
            "nested/instances/alice/profile.md", "DATA/personal.txt", "nested/logs/app.txt",
            "cache/cached.txt", "backups/source.txt", "outputs/result.txt",
            "chat_exports/export.txt", "nested/local.sqlite-wal", "nested/.env.example",
            "nested/credentials.json", "nested/conversations.json", "assets/character.PNG",
            ".wheel-venv/pyvenv.cfg", "tmp/scratch.txt", ".tmp/scratch.txt", "temp/scratch.txt",
            "verification/report.md", "local-assets/readme.md", "generated-assets/readme.md",
            "assets/character.svg", "models/weights.onnx", "models/weights.gguf", "weights.bin",
        )
        for name in names:
            self.stage(name, "synthetic content\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, "Denied paths accepted")
        identifiers = {int(number) for number in re.findall(r"^file#(\d+):", result.stderr, re.M)}
        self.assertTrue(identifiers == set(range(1, len(names) + 1)), "Not all denied index entries reported")
        self.assert_redacted(result, *names)

    def test_staged_secret_survives_working_tree_cleanup(self) -> None:
        value = "gh" + "p_" + "b" * 36
        self.stage("config.txt", value)
        (self.repo / "config.txt").write_text("clean now\n", encoding="utf-8")
        self.assert_rejected(self.check(), "github-token")

    def test_unstaged_secret_is_outside_index_scope(self) -> None:
        self.stage("config.txt", "clean staged copy\n")
        (self.repo / "config.txt").write_text("gh" + "p_" + "c" * 36, encoding="utf-8")
        (self.repo / "untracked.txt").write_bytes(b"\x00")
        self.assertEqual(self.check().returncode, 0)

    def test_all_index_entries_are_checked_not_only_staged_diff(self) -> None:
        self.stage("config.txt", "gh" + "p_" + "d" * 36)
        self.git("-c", "user.name=Synthetic Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "synthetic fixture")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")
        self.assert_rejected(self.check(), "github-token")

    def test_binary_and_non_utf8_fail_closed(self) -> None:
        self.stage("nul-byte.txt", b"safe\x00data")
        self.stage("invalid.txt", b"\xff\xfe")
        self.stage("control.txt", b"safe\x1bdata")
        result = self.check()
        self.assert_rejected(result, "binary-content")
        self.assertTrue("non-utf8-content" in result.stderr, "Non-UTF8 category missing")

    def test_oversized_blob_is_rejected(self) -> None:
        self.stage("large.txt", b"a" * (4 * 1024 * 1024 + 1))
        self.assert_rejected(self.check(), "oversized-blob")

    def test_symlink_and_submodule_index_modes_fail_closed(self) -> None:
        blob = self.git("hash-object", "-w", "--stdin", data=b"target.txt\n").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{blob},link.txt")
        # A gitlink's mode is sufficient to reject it without reading any external repository.
        self.git("update-index", "--add", "--cacheinfo", f"160000,{blob},external-module")
        result = self.check()
        self.assert_rejected(result, "unsupported-index-mode")
        self.assertEqual(result.stderr.count(": unsupported-index-mode"), 2)

    def test_unmerged_entries_fail_closed(self) -> None:
        blob = self.git("hash-object", "-w", "--stdin", data=b"plain text\n").decode().strip()
        record = f"100644 {blob} 1\tconflict.txt\n".encode()
        self.git("update-index", "--index-info", data=record)
        self.assert_rejected(self.check(), "unmerged-index-entry")

    def test_missing_blob_fails_closed(self) -> None:
        self.git("update-index", "--add", "--cacheinfo", f"100644,{'1' * 40},missing.txt")
        self.assert_rejected(self.check(), "unreadable-blob")

    def test_executable_text_is_allowed(self) -> None:
        self.stage("script.sh", "#!/bin/sh\nprintf hello\n")
        self.git("update-index", "--chmod=+x", "script.sh")
        self.assertEqual(self.check().returncode, 0)

    def test_non_repository_is_an_error_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="neurocore-not-git-") as directory:
            result = subprocess.run(
                [sys.executable, str(SCANNER), "--repo", directory], capture_output=True,
                text=True, encoding="utf-8", env=self.environment, check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertTrue("git-index-unavailable" in result.stderr, "Index error category missing")
        self.assertTrue("passed" not in result.stdout, "Index error reported success")

    def test_f01_a_same_dynamic_secret_in_filename_and_body(self) -> None:
        value = self.synthetic_token()
        name = "secrets/" + value + ".env"
        self.stage(name, value)
        result = self.check()
        for rule in ("denied-directory", "denied-filename", "github-token", "path-github-token"):
            self.assert_rejected(result, rule)
        self.assert_redacted(result, value, name)
        self.assertEqual(result.stderr.count("file#1:"), 4)

    def test_f01_b_only_path_has_sensitive_pattern(self) -> None:
        # Case-sensitive formats ensure path matching does not lowercase secrets.
        examples = (
            ("github-token", self.synthetic_token()),
            ("aws-access-key", "AK" + "IA" + secrets.token_hex(8).upper()),
            ("google-api-key", "AI" + "za" + secrets.token_hex(18)[:35]),
        )
        for rule, value in examples:
            self.stage(value + ".txt", "harmless content\n")
        result = self.check()
        for rule, value in examples:
            with self.subTest(rule=rule):
                self.assert_rejected(result, "path-" + rule)
                self.assert_redacted(result, value, value + ".txt")

    def test_f01_d_unreadable_blob_with_sensitive_path(self) -> None:
        value = self.synthetic_token()
        self.git("update-index", "--add", "--cacheinfo", f"100644,{'1' * 40},{value}.txt")
        result = self.check()
        self.assert_rejected(result, "unreadable-blob")
        self.assert_redacted(result, value)

    def test_f01_d_index_exception_does_not_render_message(self) -> None:
        value = self.synthetic_token()
        spec = importlib.util.spec_from_file_location("scanner_f01", SCANNER)
        scanner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scanner)
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["check_sensitive.py"]), \
             mock.patch.object(scanner, "git", side_effect=OSError(value)), \
             redirect_stdout(output), redirect_stderr(errors):
            code = scanner.main()
        result = subprocess.CompletedProcess([], code, output.getvalue(), errors.getvalue())
        self.assertEqual(code, 2)
        self.assertTrue("git-index-unavailable" in result.stderr, "Index error category missing")
        self.assert_redacted(result, value)

    def test_f01_d_cli_error_does_not_echo_argument(self) -> None:
        value = self.synthetic_token()
        result = subprocess.run(
            [sys.executable, str(SCANNER), "--unknown", value], capture_output=True,
            text=True, encoding="utf-8", env=self.environment, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertTrue("invalid-arguments" in result.stderr, "CLI error category missing")
        self.assert_redacted(result, value)

    def test_f01_e_failing_test_reports_do_not_echo_fixtures(self) -> None:
        value = self.synthetic_token()
        leaking = subprocess.CompletedProcess([], 1, value, value)
        wrong_status = subprocess.CompletedProcess([], 0, value, value)

        def git_failure():
            failure = subprocess.CompletedProcess(["git", value], 1, value, value)
            with mock.patch("subprocess.run", return_value=failure):
                self.git("add", value)

        def git_exception():
            with mock.patch("subprocess.run", side_effect=OSError(value)):
                self.git("add", value)

        def file_exception():
            with mock.patch.object(Path, "write_bytes", side_effect=OSError(value)):
                self.stage(value + ".txt", "harmless")

        callbacks = (
            lambda: self.assert_rejected(wrong_status, "github-token"),
            lambda: self.assert_rejected(leaking, "github-token"),
            lambda: self.assert_redacted(leaking, value),
            git_failure, git_exception, file_exception,
        )
        for index, callback in enumerate(callbacks):
            with self.subTest(case=index):
                report = io.StringIO()
                suite = unittest.TestSuite([unittest.FunctionTestCase(callback)])
                result = unittest.TextTestRunner(stream=report).run(suite)
                self.assertEqual(len(result.failures), 1, "Expected an intentional assertion failure")
                self.assertTrue(value not in report.getvalue(), "Test failure report exposed a sensitive fixture")

    def test_f02_complete_token_with_filename_prefixes_and_suffixes(self) -> None:
        value = self.synthetic_token()
        templates = (
            "{}.txt", "config-{}.txt", "config.{}.txt", "config {}.txt",
            "config_{}.txt", "说明{}.txt", "说明_{}.txt", "{}_backup.txt",
            "{}说明.txt", "config{}.txt", "{}backup.txt", "说明_{}说明.txt",
            "目录_{}/notes.txt",
        )
        names = [template.format(value) for template in templates]
        body = b"harmless fixture body\n"
        for name in names:
            self.stage(name, body)
        self.assert_indexed(names, body)
        result = self.check()
        self.assert_rejected(result, "path-github-token")
        detected = {int(n) for n in re.findall(r"^file#(\d+): path-github-token$", result.stderr, re.M)}
        self.assertTrue(detected == set(range(1, len(names) + 1)), "A filename boundary case escaped detection")
        self.assert_redacted(result, value, *names)

    def test_f02_filename_case_sensitivity_preserves_core_rules(self) -> None:
        github = self.synthetic_token()
        aws_payload = secrets.token_hex(8).upper()
        google_payload = secrets.token_hex(18)[:35]
        examples = (
            ("github-token", github, True),
            ("github-token", github[:4] + github[4:].swapcase(), True),
            ("github-token", github.upper(), False),
            ("aws-access-key", "AK" + "IA" + aws_payload, True),
            ("aws-access-key", "ak" + "ia" + aws_payload, False),
            ("aws-access-key", "AK" + "IA" + "a" + aws_payload[1:], False),
            ("google-api-key", "AI" + "za" + google_payload, True),
            ("google-api-key", "ai" + "za" + google_payload, False),
        )
        names = [f"case-{index}/说明_{value}说明.txt" for index, (_, value, _) in enumerate(examples)]
        body = b"harmless fixture body\n"
        for name in names:
            self.stage(name, body)
        indexed = self.assert_indexed(names, body)
        expected = {(indexed.index(name.encode("utf-8")) + 1, "path-" + rule)
                    for name, (rule, _, rejected) in zip(names, examples) if rejected}
        result = self.check()
        actual = {(int(number), rule) for number, rule in
                  re.findall(r"^file#(\d+): ([a-z-]+)$", result.stderr, re.M)}
        self.assertEqual(result.returncode, 1, "Sensitive filename cases accepted")
        self.assertTrue(actual == expected, "Filename case rules changed or added a false positive")
        self.assert_redacted(result, *names, *(value for _, value, _ in examples))

    def test_f02_normal_and_incomplete_filenames_still_pass(self) -> None:
        short_value = "gh" + "p_" + secrets.token_hex(9) + "a"
        names = ["config_api_key_notes.txt", "github_token_notes.txt", "说明_配置.txt",
                 "token_backup.txt", "config_readme.txt", "config_" + short_value + "说明.txt"]
        body = b"harmless fixture body\n"
        for name in names:
            self.stage(name, body)
        self.assert_indexed(names, body)
        result = self.check()
        self.assertEqual(result.returncode, 0, "A normal or incomplete filename was rejected")
        self.assertTrue(not result.stderr, "Clean fixture reported an error")
        self.assert_redacted(result, *names, short_value)

    def test_f02_body_word_boundary_semantics_are_unchanged(self) -> None:
        spec = importlib.util.spec_from_file_location("scanner_f02", SCANNER)
        scanner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scanner)
        value = self.synthetic_token()
        examples = ((value, True), ("config-" + value, True), (value + "backup", True),
                    ("config_" + value, False), ("说明" + value, False),
                    (value + "_backup", False), (value + "说明", False))
        for index, (body, expected) in enumerate(examples):
            with self.subTest(case=index):
                found = "github-token" in scanner.content_violations(body.encode("utf-8"))
                self.assertTrue(found == expected, "Original body matching semantics changed")

    def test_f02_sensitive_body_only_is_still_rejected(self) -> None:
        value = self.synthetic_token()
        self.stage("plain.txt", value)
        self.assert_indexed(["plain.txt"], value.encode("utf-8"))
        result = self.check()
        self.assert_rejected(result, "github-token")
        self.assertTrue("file#1: github-token" in result.stderr.splitlines(), "Body finding missing")
        self.assertTrue("path-github-token" not in result.stderr, "Harmless path was misclassified")
        self.assert_redacted(result, value, "plain.txt")

    def test_f02_sensitive_body_and_embedded_filename_are_rejected(self) -> None:
        value = self.synthetic_token()
        name = "说明_" + value + "_backup.txt"
        self.stage(name, value)
        self.assert_indexed([name], value.encode("utf-8"))
        result = self.check()
        self.assert_rejected(result, "path-github-token")
        self.assertTrue("file#1: github-token" in result.stderr.splitlines(), "Body finding missing")
        self.assert_redacted(result, value, name)

    def test_f02_index_assertion_failure_does_not_echo_filename(self) -> None:
        value = self.synthetic_token()
        report = io.StringIO()
        callback = lambda: self.assert_indexed(["说明_" + value + ".txt"], b"harmless")
        suite = unittest.TestSuite([unittest.FunctionTestCase(callback)])
        result = unittest.TextTestRunner(stream=report).run(suite)
        self.assertEqual(len(result.failures), 1, "Expected an intentional index assertion failure")
        self.assertTrue(value not in report.getvalue(), "Index assertion report exposed a sensitive fixture")


if __name__ == "__main__":
    unittest.main()
