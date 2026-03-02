#!/usr/bin/env python3
"""Dependency Completeness Audit - verify every package in pyproject.toml imports."""

import importlib
import sys
import tomllib
from pathlib import Path

# Map pip names to import names
PIP_TO_IMPORT = {
    "python-telegram-bot": "telegram",
    "pyyaml": "yaml",
    "python-multipart": "multipart",
    "python-dotenv": "dotenv",
    "pydantic-settings": "pydantic_settings",
    "prometheus-client": "prometheus_client",
    "slack-sdk": "slack",
    "aiohttp": "aiohttp",
    "faster-whisper": "faster_whisper",
    "redis": "redis",
    "scrapling": "scrapling",
    "playwright": "playwright",
    "curl-cffi": "curl_cffi",
    "browserforge": "browserforge",
    "msgspec": "msgspec",
    "patchright": "patchright",
    "pytest": "pytest",
    "pytest-asyncio": "pytest_asyncio",
    "pytest-cov": "pytest_cov",
    "ruff": "ruff",
    "mypy": "mypy",
    "GitPython": "git",
    "docker": "docker",
    "psutil": "psutil",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
    "Pillow": "PIL",
    "pillow": "PIL",
    "qrcode": "qrcode",
    "openpyxl": "openpyxl",
    "python-docx": "docx",
    "python-pptx": "pptx",
    "pypdf": "pypdf",
    "xmltodict": "xmltodict",
    "toml": "toml",
    "httpx": "httpx",
    "aiofiles": "aiofiles",
    "click": "click",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "Pillow": "PIL",
}

def extract_dependencies():
    """Extract all dependencies from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)

    deps = set()
    optional_deps = data.get("project", {}).get("optional-dependencies", {})

    # Add main dependencies
    for dep in data.get("project", {}).get("dependencies", []):
        # Extract package name (before >=, ==, etc.)
        pkg = dep.split(">")[0].split("=")[0].split("<")[0].strip()
        # Skip extras syntax like uvicorn[standard]
        if "[" not in pkg:
            deps.add(pkg)

    # Add optional dependencies
    for group, packages in optional_deps.items():
        for dep in packages:
            pkg = dep.split(">")[0].split("=")[0].split("<")[0].strip()
            # Skip extras syntax like qrcode[pil]
            if "[" not in pkg:
                deps.add(pkg)

    return deps

def verify_import(pkg_name):
    """Try to import a package and report status."""
    import_name = PIP_TO_IMPORT.get(pkg_name, pkg_name.replace("-", "_").lower())

    # Handle special cases
    if pkg_name == "Pillow":
        import_name = "PIL"
    elif pkg_name == "aiofiles":
        import_name = "aiofiles"
    elif pkg_name == "click":
        import_name = "click"

    try:
        importlib.import_module(import_name)
        return "OK", None
    except ImportError as e:
        return "MISSING", str(e)
    except Exception as e:
        return "ERROR", str(e)

def main():
    deps = extract_dependencies()

    ok_count = 0
    missing_count = 0
    error_count = 0

    print("DEPENDENCY COMPLETENESS AUDIT")
    print("=" * 60)

    for pkg in sorted(deps):
        status, error = verify_import(pkg)
        if status == "OK":
            ok_count += 1
            print(f"OK: {pkg}")
        elif status == "MISSING":
            missing_count += 1
            print(f"MISSING: {pkg} - {error}")
        else:
            error_count += 1
            print(f"ERROR: {pkg} - {error}")

    print("=" * 60)
    print(f"SUMMARY: {ok_count} OK, {missing_count} missing, {error_count} error")

    return 0 if missing_count == 0 and error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
