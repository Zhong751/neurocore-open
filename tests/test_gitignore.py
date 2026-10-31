"""Exercise the actual .gitignore using Git, without changing the source index."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


IGNORE_FILE = Path(__file__).resolve().parents[1] / ".gitignore"


@unittest.skipUnless(shutil.which("git"), "Git is required")
class GitignoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="neurocore-ignore-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.environment = os.environ.copy()
        self.environment.update(
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
            GIT_CONFIG_VALUE_0=str(self.repo),
        )
        self.git("init", "--quiet")
        shutil.copyfile(IGNORE_FILE, self.repo / ".gitignore")

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], capture_output=True, text=True,
            encoding="utf-8", env=self.environment, check=False,
        )

    def test_sensitive_and_generated_paths_are_ignored(self) -> None:
        paths = (
            ".env", ".env.local", "nested/.env.example", "nested/production.env",
            "credentials/service.json", "nested/secrets.toml", ".ssh/id_ed25519",
            "instances/alice/settings.json", "nested/user-data/profile.json", "data/profile.json",
            "runtime/session.txt", "databases/state.db", "nested/state.sqlite3-wal",
            "logs/server.log.1", "nested/cache/entry.txt", "src/neurocore/__pycache__/x.pyc",
            ".pytest_cache/results", ".venv/pyvenv.cfg", "backups/config.toml",
            "config.toml.bak", "outputs/report.md", "nested/chat_exports/thread.json",
            "exports/archive.jsonl", "nested/conversations.json", "nested/messages.jsonl",
            "assets/characters/avatar.png", "assets/characters/person.glb",
            "characters/portrait.psd", "models/weights.safetensors", "private.zip",
            "dist/neurocore.whl", "build/package.txt", "package.egg-info/PKG-INFO",
            ".wheel-venv/pyvenv.cfg", "tmp/scratch.txt", ".tmp/scratch.txt", "temp/scratch.txt",
            "verification/report.md", "local-assets/readme.md", "generated-assets/readme.md",
            "assets/character.svg", "models/weights.onnx", "models/weights.gguf", "weights.bin",
        )
        for path in paths:
            with self.subTest(path=path):
                result = self.git("check-ignore", "--no-index", "--quiet", "--", path)
                self.assertEqual(result.returncode, 0, path + ": " + result.stderr)

    def test_public_source_docs_configuration_and_lockfiles_are_allowed(self) -> None:
        paths = (
            ".gitignore", "README.md", "LICENSE", "pyproject.toml", "uv.lock",
            ".github/workflows/ci.yml", "src/neurocore/__init__.py", "src/neurocore/cli.py",
            "scripts/check_sensitive.py", "tests/test_sensitive.py", "tests/test_gitignore.py",
            "docs/security_checks.md", "docs/architecture.md", "examples/settings.toml",
            "src/neurocore/models/__init__.py",
        )
        for path in paths:
            with self.subTest(path=path):
                result = self.git("check-ignore", "--no-index", "--quiet", "--", path)
                self.assertEqual(result.returncode, 1, path + ": " + result.stderr)


if __name__ == "__main__":
    unittest.main()
