"""Root conftest — ensure the src-layout package is importable without pip install."""

import sys
from pathlib import Path

# Add src/ to the front of sys.path so `import portal` resolves
# regardless of whether the package is installed via pip/uv.
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
