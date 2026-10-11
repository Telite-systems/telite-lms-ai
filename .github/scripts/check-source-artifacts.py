"""Reject tracked runtime archives and credential files without reading contents.

This is a source-hygiene gate, not a secret scanner. Run from the repository root.
Uses the Git index so force-added ignored files are checked too.
"""

from __future__ import annotations

from pathlib import PurePosixPath
import subprocess
import sys


FORBIDDEN_SUFFIXES = (
    ".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".rar", ".dump", ".bak",
    ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p8", ".p12", ".pfx",
    ".jks", ".keystore",
)


def forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name.lower()
    parts = PurePosixPath(normalized.lower()).parts
    if "backups" in parts or "moodledata" in parts or "pgdata" in parts:
        return True
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name in {"moodle.sql", "credentials.json", "cookies.txt", "pw.txt"}:
        return True
    if name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        return True
    return name.endswith(FORBIDDEN_SUFFIXES)


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True,
    )
    paths = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    findings = sorted(path for path in paths if path and forbidden(path))
    if findings:
        print("Source artifact check failed: remove these tracked paths.")
        for path in findings:
            print(f"  {ascii(path)}")
        print("Store operational backups in encrypted restricted storage outside Git.")
        return 1
    print("Source artifact check passed (tracked paths only; no content scan).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
