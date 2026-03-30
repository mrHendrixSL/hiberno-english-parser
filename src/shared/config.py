"""Configuration helpers.

This module provides simple convenience functions for loading YAML
configuration files. Separating configuration from code is critical for
reproducibility and allows parameters to be modified without editing
source files. Configurations are expected to live in the ``configs/``
folder at the project root, but any path can be supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass
class Config:
    """A thin wrapper over a mapping loaded from YAML.

    Instances of this class behave like dictionaries and expose
    attributes corresponding to top‑level keys. Nested keys can be
    accessed via indexing or attribute access. Missing keys raise
    ``KeyError``.
    """

    data: Mapping[str, Any]

    def __getattr__(self, item: str) -> Any:
        try:
            return self.data[item]
        except KeyError:
            raise AttributeError(item)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def load_config(path: str | Path) -> Config:
    """Load a YAML configuration file.

    Returns a :class:`Config` instance wrapping the loaded data. Raises
    ``FileNotFoundError`` if the file does not exist and ``yaml.YAMLError``
    for malformed YAML.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Config(data)
