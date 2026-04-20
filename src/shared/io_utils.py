"""
io_utils.py
===========
Shared JSON and filesystem helpers.
"""

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path, default: Any = None) -> Any:
    """Load a JSON file.  Returns *default* if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any, indent: int = 2) -> None:
    """Serialise *data* to a JSON file, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def ensure_dir(path: str | Path) -> Path:
    """Create *path* and all parents.  Return the Path object."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
