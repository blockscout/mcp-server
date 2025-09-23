"""Import all handlers in this package to trigger registration with the dispatcher."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

_pkg_path = Path(__file__).parent
for module_info in iter_modules([str(_pkg_path)]):
    if module_info.ispkg or module_info.name.startswith("_") or module_info.name == "__init__":
        continue
    import_module(f"{__name__}.{module_info.name}")
