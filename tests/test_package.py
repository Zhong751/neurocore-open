"""Verify the installed distribution, not imports from the repository root."""
import importlib.metadata
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PackageTests(unittest.TestCase):
    def test_imports_from_isolated_process_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import neurocore; import neurocore.core, neurocore.perception, "
                 "neurocore.models, neurocore.api, neurocore.memory; print('import-ok')"],
                cwd=directory, capture_output=True, text=True, check=True,
            )
        self.assertEqual(result.stdout.strip(), "import-ok")

    def test_distribution_metadata_and_license_declaration(self):
        distribution = importlib.metadata.distribution("neurocore")
        metadata = distribution.metadata
        self.assertEqual(metadata["Version"], "0.0.0.dev0")
        self.assertEqual(metadata["Requires-Python"].replace(" ", ""), ">=3.12,<3.13")
        self.assertEqual(metadata["License-Expression"], "Apache-2.0")
        self.assertFalse(metadata.get_all("Requires-Dist"))
        self.assertEqual(metadata.get_all("License-File"), ["LICENSE"])

    def test_source_license_is_complete_canonical_text(self):
        license_path = Path(__file__).resolve().parents[1] / "LICENSE"
        content = license_path.read_text(encoding="utf-8")
        self.assertIn("END OF TERMS AND CONDITIONS", content)
        self.assertIn("APPENDIX: How to apply the Apache License", content)
        self.assertEqual(
            hashlib.sha256(license_path.read_bytes()).hexdigest(),
            "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        )


if __name__ == "__main__":
    unittest.main()
