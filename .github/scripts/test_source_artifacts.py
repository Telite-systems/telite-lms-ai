"""Exercise the source gate against actual Git indexes, including forced adds."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("check-source-artifacts.py")
spec = importlib.util.spec_from_file_location("source_artifacts", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SourceArtifactsTests(unittest.TestCase):
    def test_sensitive_path_classes(self):
        for path in (
            "backups/backup.txt", "release.ZIP", "nested/data.tar.gz",
            "db/snapshot.dump", "local.sqlite3", "tenant/.env.production",
            "tenant/.env", "auth/signing.pem", "id_ed25519", "moodle.sql",
        ):
            with self.subTest(path=path):
                self.assertTrue(gate.forbidden(path))

    def test_source_and_synthetic_examples_allowed(self):
        for path in (
            ".env.example", "nested/.env.example", "docker/sql/provision.sql",
            "app/core/security.py", "docs/security-remediation.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(gate.forbidden(path))

    def test_forced_ignored_archive_fails_and_staged_removal_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / ".gitignore").write_text("*.zip\n", encoding="utf-8")
            (root / ".env.example").write_text("EXAMPLE=synthetic\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore", ".env.example"], cwd=root, check=True)

            def run_gate():
                return subprocess.run(
                    [__import__("sys").executable, str(SCRIPT)], cwd=root,
                    capture_output=True, text=True, check=False,
                )

            self.assertEqual(run_gate().returncode, 0)
            (root / "backup.zip").write_bytes(b"synthetic archive fixture")
            subprocess.run(["git", "add", "-f", "backup.zip"], cwd=root, check=True)
            result = run_gate()
            self.assertEqual(result.returncode, 1)
            self.assertIn("backup.zip", result.stdout)
            self.assertNotIn("synthetic archive fixture", result.stdout)
            subprocess.run(["git", "rm", "--cached", "-f", "backup.zip"], cwd=root, check=True, capture_output=True)
            self.assertEqual(run_gate().returncode, 0)


if __name__ == "__main__":
    unittest.main()
