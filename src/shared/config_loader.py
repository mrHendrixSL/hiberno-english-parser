"""
config_loader.py
================
Load and validate YAML configuration files.
Paths inside configs are resolved relative to the repository root
(the directory containing the configs/ folder).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


def _repo_root() -> Path:
    """Resolve the repository root as the parent of the configs/ directory.

    Walks up from this file's location until it finds a configs/ directory,
    falling back to the current working directory.
    """
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "configs").is_dir():
            return parent
    return Path.cwd()


REPO_ROOT: Path = _repo_root()


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load a YAML config file.

    *config_path* may be absolute or relative to the repository root.
    """
    p = Path(config_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def resolve_path(cfg_value: str, base: Path | None = None) -> Path:
    """Resolve a path value from a config dict entry.

    If *cfg_value* is absolute it is returned as-is.
    Otherwise it is resolved relative to *base* (defaults to REPO_ROOT).
    """
    p = Path(cfg_value)
    if p.is_absolute():
        return p
    return (base or REPO_ROOT) / p
