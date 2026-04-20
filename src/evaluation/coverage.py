"""
coverage.py
===========
Recompute token and character coverage from scratch for both rule-based
and LLM outputs in the evaluation DataFrame.

Uses the canonical COVERAGE_STOPWORDS and normalise_fullwidth from
src.shared.normalisation so coverage computation is consistent across
all modules.
"""

from __future__ import annotations

import re

import pandas as pd

from src.shared.normalisation import normalise_fullwidth, COVERAGE_STOPWORDS
from src.shared.schema import COVERAGE_FIELDS_EVAL


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> set[str]:
    """Tokenise a string for coverage computation."""
    text = normalise_fullwidth(text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return {
        t for t in text.split()
        if len(t) > 2 and not t.isdigit() and t not in COVERAGE_STOPWORDS
    }


def _field_tokens(value) -> set[str]:
    """Extract tokens from any field value."""
    import math

    if value is None:
        return set()
    if isinstance(value, float) and math.isnan(value):
        return set()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.extend(str(v) for v in item.values() if v is not None)
            else:
                parts.append(str(item))
        return _tokenise(" ".join(parts))
    if isinstance(value, dict):
        return _tokenise(" ".join(str(v) for v in value.values() if v is not None))
    return _tokenise(str(value))


def _field_chars(value) -> int:
    """Count total characters across a field value."""
    import math

    if value is None:
        return 0
    if isinstance(value, float) and math.isnan(value):
        return 0
    if isinstance(value, list):
        return sum(len(str(v)) for v in value)
    if isinstance(value, dict):
        return sum(len(str(v)) for v in value.values())
    return len(str(value))


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------

def compute_coverage(full_text: str, record: dict) -> dict:
    """Compute token and character coverage metrics for one record.

    Returns ``{"coverage_pct": float, "coverage_char_pct": float}``.
    """
    if not full_text:
        return {"coverage_pct": 100.0, "coverage_char_pct": 100.0}

    src_tokens    = _tokenise(full_text)
    parsed_tokens: set[str] = set()
    for f in COVERAGE_FIELDS_EVAL:
        parsed_tokens |= _field_tokens(record.get(f))

    if not src_tokens:
        covered_pct = 100.0
    else:
        uncovered   = src_tokens - parsed_tokens
        covered_pct = round(
            100 * (len(src_tokens) - len(uncovered)) / len(src_tokens), 1
        )

    content_chars = sum(_field_chars(record.get(f)) for f in COVERAGE_FIELDS_EVAL)
    char_pct = (
        min(100.0, round(100 * content_chars / len(full_text), 1))
        if len(full_text) > 0
        else 100.0
    )

    return {"coverage_pct": covered_pct, "coverage_char_pct": char_pct}


# ---------------------------------------------------------------------------
# DataFrame integration
# ---------------------------------------------------------------------------

def add_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Add coverage_pct_Rule, coverage_pct_LLM, coverage_char_pct_Rule,
    coverage_char_pct_LLM columns to the merged DataFrame."""
    rb_pcts:      list[float] = []
    llm_pcts:     list[float] = []
    rb_char_pcts: list[float] = []
    llm_char_pcts:list[float] = []

    for row in df.itertuples(index=False):
        full_text = row.full_text or ""
        rb_record  = {f: getattr(row, f"{f}_Rule", None) for f in COVERAGE_FIELDS_EVAL}
        llm_record = {f: getattr(row, f"{f}_LLM",  None) for f in COVERAGE_FIELDS_EVAL}

        rb_cov  = compute_coverage(full_text, rb_record)
        llm_cov = compute_coverage(full_text, llm_record)

        rb_pcts.append(rb_cov["coverage_pct"])
        llm_pcts.append(llm_cov["coverage_pct"])
        rb_char_pcts.append(rb_cov["coverage_char_pct"])
        llm_char_pcts.append(llm_cov["coverage_char_pct"])

    df = df.copy()
    df["coverage_pct_Rule"]      = rb_pcts
    df["coverage_pct_LLM"]       = llm_pcts
    df["coverage_char_pct_Rule"] = rb_char_pcts
    df["coverage_char_pct_LLM"]  = llm_char_pcts
    return df
