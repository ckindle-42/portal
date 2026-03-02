#!/usr/bin/env python3
"""Module Import Audit - verify every .py file in src/portal/ imports."""

import importlib
import sys
from pathlib import Path

def get_all_python_modules(base_path):
    """Get all .py files in src/portal/ directory."""
    modules = []
    base = Path(base_path)

    for py_file in sorted(base.rglob("*.py")):
        # Skip __pycache__ and __init__.py for now
        if "__pycache__" in str(py_file):
            continue

        # Compute module path relative to src/portal/
        # base_path should be src/portal/
        rel_path = py_file.relative_to(base)
        module_parts = list(rel_path.parts)

        # Convert to module dotted path (e.g., "agent.core")
        # Remove .py extension
        if module_parts[-1].endswith(".py"):
            module_parts[-1] = module_parts[-1][:-3]

        if module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]

        if module_parts:
            modules.append(".".join(module_parts))

    return modules

def try_import(module_name):
    """Try to import a portal module."""
    try:
        full_name = f"portal.{module_name}"
        mod = importlib.import_module(full_name)
        return "OK", None
    except ImportError as e:
        return "MISSING", str(e)
    except Exception as e:
        return "ERROR", str(e)

def main():
    src_path = Path("src/portal")
    modules = get_all_python_modules(src_path)

    ok_count = 0
    missing_count = 0
    error_count = 0

    print("PORTAL MODULE IMPORT AUDIT")
    print("=" * 60)

    for module in modules:
        status, error = try_import(module)
        if status == "OK":
            ok_count += 1
            print(f"OK: portal.{module}")
        elif status == "MISSING":
            missing_count += 1
            print(f"MISSING: portal.{module} - {error}")
        else:
            error_count += 1
            print(f"ERROR: portal.{module} - {error}")

    print("=" * 60)
    print(f"SUMMARY: {ok_count} OK, {missing_count} missing, {error_count} error")

    return 0 if missing_count == 0 and error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
