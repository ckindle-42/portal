#!/usr/bin/env python3
"""
Portal release helper.

Automates the manual steps required to cut a new release:
  1. Validates the new version string (semver, must be > current).
  2. Checks that CHANGELOG.md has a section for the new version.
  3. Updates the version in pyproject.toml and src/portal/__init__.py.
  4. Creates a git commit and an annotated tag.
  5. Reminds you to push both so the release workflow fires.

The actual release archive is built and uploaded to GitHub by the
.github/workflows/release.yml workflow when the tag reaches the remote.
There are no pre-compiled artefacts — end users run Portal directly from
the extracted source on their own machines.

Usage:
    python scripts/release.py <new-version>

Example:
    python scripts/release.py 1.1.0
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "portal" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, check=check, capture_output=True, text=True)


def _current_version() -> str:
    text = PYPROJECT.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("ERROR: Could not find version in pyproject.toml")
    return m.group(1)


def _validate_semver(v: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"ERROR: '{v}' is not a valid semver (expected X.Y.Z)")


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def _check_changelog(version: str) -> None:
    text = CHANGELOG.read_text()
    if f"## [{version}]" not in text:
        raise SystemExit(
            f"ERROR: CHANGELOG.md has no section for [{version}].\n"
            f"Add a '## [{version}] - YYYY-MM-DD' section before running this script."
        )


def _bump_pyproject(old: str, new: str) -> None:
    text = PYPROJECT.read_text()
    updated = text.replace(f'version = "{old}"', f'version = "{new}"', 1)
    if updated == text:
        raise SystemExit("ERROR: Could not update version in pyproject.toml")
    PYPROJECT.write_text(updated)


def _bump_init(old: str, new: str) -> None:
    text = INIT.read_text()
    updated = re.sub(
        r'(__version__\s*=\s*)"[^"]+"',
        f'\\g<1>"{new}"',
        text,
        count=1,
    )
    # Also update the docstring version comment if present
    updated = re.sub(
        r'(Version:\s*)' + re.escape(old),
        f'\\g<1>{new}',
        updated,
    )
    if updated == text:
        raise SystemExit("ERROR: Could not update __version__ in src/portal/__init__.py")
    INIT.write_text(updated)


def _git_commit_and_tag(version: str) -> None:
    tag = f"v{version}"

    # Stage the two version files
    _run(["git", "add", str(PYPROJECT), str(INIT)])

    result = _run(["git", "diff", "--cached", "--name-only"])
    if not result.stdout.strip():
        raise SystemExit("ERROR: No staged changes — version files were not modified?")

    _run(["git", "commit", "-m", f"chore: release v{version}"])
    _run(["git", "tag", "-a", tag, "-m", f"Portal {tag}"])
    print(f"  Created commit and tag {tag}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    new_version = sys.argv[1].lstrip("v")  # accept "v1.1.0" or "1.1.0"
    _validate_semver(new_version)

    old_version = _current_version()

    if _version_tuple(new_version) <= _version_tuple(old_version):
        raise SystemExit(
            f"ERROR: New version {new_version} must be greater than current {old_version}"
        )

    print(f"Releasing {old_version} → {new_version}")

    print("  Checking CHANGELOG.md …")
    _check_changelog(new_version)

    print("  Checking working tree is clean …")
    result = _run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        raise SystemExit(
            "ERROR: Working tree is not clean.\n"
            "Commit or stash your changes before releasing."
        )

    print("  Bumping version in pyproject.toml …")
    _bump_pyproject(old_version, new_version)

    print("  Bumping version in src/portal/__init__.py …")
    _bump_init(old_version, new_version)

    print("  Creating git commit and tag …")
    _git_commit_and_tag(new_version)

    tag = f"v{new_version}"
    print(
        f"\nDone. Push the commit and tag to trigger the release workflow:\n"
        f"\n"
        f"    git push origin HEAD && git push origin {tag}\n"
        f"\n"
        f"The workflow will build portal-{tag}.zip and attach it to the\n"
        f"GitHub Release automatically."
    )


if __name__ == "__main__":
    main()
