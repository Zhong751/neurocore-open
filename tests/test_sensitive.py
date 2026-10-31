"""End-to-end gate tests using only independent temporary Git repositories."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCANNER = Path(__file__).resolve().parents[1] / "scripts" / "check_sensitive.py"


@unittest.skipUnless(shutil.which("git"), "Git is required")
class SensitiveIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="neurocore-sensitive-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        # Scope ownership permission to this disposable repository; never alter global config.
        self.environment = os.environ.copy()
        self.environment.update(
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
            GIT_CONFIG_VALUE_0=str(self.repo),
        )
        self.git("init", "--quiet")

    def git(self, *args: str, data: bytes | None = None) -> bytes:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args], input=data, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=self.environment, check=True,
        )
        return result.stdout

    def stage(self, name: str, content: str | bytes) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        self.git("add", "--force", "--", name)

    def check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCANNER), "--repo", str(self.repo)],
            capture_output=True, text=True, encoding="utf-8", env=self.environment,
            check=False,
        )

    def assert_rejected(self, result: subprocess.CompletedProcess[str], rule: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(rule, result.stderr)
        self.assertNotIn("passed", result.stdout)

    def test_clean_source_docs_and_lock_hashes_pass(self) -> None:
        self.stage("src/neurocore/example.py", 'print("hello")\n')
        self.stage("src/neurocore/models/__init__.py", '"""Public data models."""\n')
        self.stage("docs/guide.md", "# Public guide\n中文文档。\n")
        self.stage("uv.lock", 'version = 1\nhash = "sha256:' + "a0" * 32 + '"\n')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all Git-index entries checked", result.stdout)

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
                self.assertNotIn(value, result.stdout + result.stderr)

    def test_private_key_headers_are_detected(self) -> None:
        for index, kind in enumerate(("", "RSA ", "EC ", "OPENSSH ", "ENCRYPTED ")):
            value = "-----BE" + "GIN " + kind + "PRIVATE " + "KEY-----"
            self.stage(f"key_header_{index}.txt", value)
        result = self.check()
        self.assert_rejected(result, "private-key")
        self.assertEqual(result.stderr.count(": private-key"), 5)
        self.assertNotIn("-----BEGIN", result.stderr)

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
        self.assertNotIn(value, result.stdout + result.stderr)

    def test_placeholders_and_runtime_environment_references_pass(self) -> None:
        name = "API" + "_KEY"
        values = (
            '""', '"REPLACE_ME"', '"<PROVIDER_KEY>"', '"${PROVIDER_KEY}"',
            "None", 'os.environ["PROVIDER_KEY"]', 'os.getenv("PROVIDER_KEY")',
            "process.env.PROVIDER_KEY",
        )
        self.stage("examples.txt", "\n".join(name + " = " + value for value in values))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

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
        self.assertEqual(result.returncode, 1, result.stderr)
        for name in names:
            with self.subTest(path=name):
                self.assertIn(name, result.stderr)

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
        self.assertIn("non-utf8-content", result.stderr)

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
        self.assertIn("git-index-unavailable", result.stderr)
        self.assertNotIn("passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
