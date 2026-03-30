"""Utility functions for the Hiberno‑English parser project.

This module centralises a number of helper functions used throughout the
repository. Keeping common helpers in one place improves testability and
reduces duplication across the rule‑based, GenAI and evaluation code.

Functions include simple type coercion, normalisation, list utilities
and hashing. Where possible, helpers are pure and side‑effect free.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Dict, List

import pandas as pd


def canonical_value(v: Any) -> Any:
    """Recursively normalise a value for stable hashing or comparison.

    - Floats that are NaN become None.
    - None remains None.
    - Lists and dictionaries are normalised element‑wise.
    - All other values are returned unchanged.
    """
    if isinstance(v, float) and pd.isna(v):
        return None
    if v is None:
        return None
    if isinstance(v, list):
        return [canonical_value(x) for x in v]
    if isinstance(v, dict):
        return {k: canonical_value(v[k]) for k in sorted(v)}
    return v


def hash_text(text: Any) -> str:
    """Return a SHA‑256 hash of the provided text.

    The input is coerced to string; missing values produce an empty
    string. This helper is used to create stable identifiers for source
    paragraphs and parsed payloads.
    """
    if text is None or (isinstance(text, float) and pd.isna(text)):
        s = ""
    else:
        s = str(text)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def is_nullish(value: Any) -> bool:
    """Return True if a value should be considered null/empty.

    Handles None, NaN, empty strings, empty iterables and empty dicts.
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
        return True
    return False


def ensure_list(value: Any) -> List[Any]:
    """Ensure the returned value is a list.

    - None or other nullish values return an empty list.
    - Existing lists are returned unchanged.
    - All other values are wrapped in a single‑element list.
    """
    if is_nullish(value):
        return []
    if isinstance(value, list):
        return value
    return [value]


def unique_keep_order(items: Iterable[Any]) -> List[Any]:
    """Deduplicate a sequence while preserving the original order.

    Elements are compared using a JSON string representation so that
    dictionaries and lists are compared by value rather than identity.
    """
    seen = set()
    out: List[Any] = []
    for item in items:
        if isinstance(item, (dict, list)):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        else:
            key = item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def normalize_unicode(text: str) -> str:
    """Normalise a string to NFKC form.

    This collapses compatibility characters and ensures consistent
    representation for comparison.
    """
    return unicodedata.normalize("NFKC", text)


def clean_text(value: Any) -> str | None:
    """Normalise arbitrary values into clean strings.

    - None or nullish values return None.
    - Strings are normalised for unicode, collapsed whitespace and
      trimmed.
    - Non‑string values are coerced to string and cleaned similarly.
    """
    if is_nullish(value):
        return None
    text = str(value)
    text = normalize_unicode(text)
    # replace non‑breaking spaces with regular spaces
    text = text.replace("\u00a0", " ")
    # collapse consecutive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_list_text(value: Any) -> List[str]:
    """Clean a list of values and return unique strings.

    Each element is cleaned via `clean_text`. Nullish values are
    discarded and duplicates (by exact string) are removed while
    preserving order.
    """
    cleaned = [clean_text(x) for x in ensure_list(value)]
    return unique_keep_order([x for x in cleaned if x is not None])


def normalize_text_for_match(value: Any) -> str:
    """Prepare text for case‑insensitive matching.

    Performs unicode normalisation, collapsing of quotes and dashes,
    lowercasing and whitespace compression. Useful for exact match
    comparisons between rule and GenAI outputs.
    """
    text = clean_text(value) or ""
    text = text.casefold()
    # normalise fancy quotes and dashes
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def exact_text_match(left: Any, right: Any) -> bool:
    """Return True if two values are exact textual matches after normalisation."""
    return normalize_text_for_match(left) == normalize_text_for_match(right)


def exact_list_match(left: Any, right: Any) -> bool:
    """Return True if two lists of strings match exactly after cleaning."""
    return clean_list_text(left) == clean_list_text(right)
