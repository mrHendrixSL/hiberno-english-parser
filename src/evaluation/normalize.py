"""Normalisation routines for rule‑based and GenAI outputs.

This module contains helper functions for transforming raw parser
outputs into a canonical form suitable for comparison and evaluation.
It avoids altering the underlying semantics of the dictionary entries
and instead focuses on cleaning whitespace, unifying lists and
standardising casing.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

import pandas as pd

from ..shared.utils import (
    clean_text,
    clean_list_text,
    is_nullish,
    unique_keep_order,
    exact_text_match,
    exact_list_match,
)


# ---------------------------------------------------------------------------
# Generic helpers

def read_jsonl(path: str | Path) -> pd.DataFrame:
    """Load a JSONL file into a DataFrame."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def safe_int_from_id(value: Any) -> int | None:
    """Extract an integer from a string ID or return None."""
    if is_nullish(value):
        return None
    text = str(value).strip()
    match = re.search(r"(\d+)$", text)
    if match:
        return int(match.group(1))
    try:
        return int(text)
    except ValueError:
        return None


def clean_pronunciations(values: Any) -> List[str]:
    items = clean_list_text(values)
    out: List[str] = []
    for item in items:
        item = item.strip().strip("/")
        item = clean_text(item)
        if item:
            out.append(item)
    return unique_keep_order(out)


def clean_pos(values: Any) -> List[str]:
    return unique_keep_order([x.casefold() for x in clean_list_text(values)])


def clean_cross_refs(values: Any) -> List[str]:
    return unique_keep_order([x.upper() for x in clean_list_text(values)])


def clean_examples(values: Any) -> List[str]:
    return clean_list_text(values)


def clean_region_values(values: Any) -> List[str]:
    cleaned: List[str] = []
    for item in clean_list_text(values):
        if isinstance(item, dict):
            for v in item.values():
                text = clean_text(v)
                if text:
                    cleaned.append(text)
        else:
            text = clean_text(item)
            if text:
                cleaned.append(text)
    return unique_keep_order(cleaned)


def build_rule_pronunciations(row: pd.Series, columns: List[str]) -> List[str]:
    values = [row.get(col) for col in columns]
    return clean_pronunciations(values)


# ---------------------------------------------------------------------------
# Normalisation functions

# Shared canonical ordering of fields in the evaluation output
CORE_FIELDS = [
    "entry_id",
    "source_text",
    "headword_raw",
    "headword",
    "variant_forms_raw",
    "variant_forms",
    "pronunciations",
    "part_of_speech",
    "definition",
    "examples",
    "etymology",
    "cross_references",
    "region_mentions",
    "needs_review",
]


def normalize_rule(rule_df: pd.DataFrame, pos_columns: List[str], pos_col_name: str) -> pd.DataFrame:
    """Normalise the raw rule‑based output into a canonical schema."""
    out_rows = []
    for _, row in rule_df.iterrows():
        record = {
            "entry_id": safe_int_from_id(row.get("entry_id")),
            "source_text": clean_text(row.get("source_text")),
            "headword_raw": clean_text(row.get("headword_raw")),
            "headword": clean_text(row.get("headword")),
            "variant_forms_raw": clean_text(row.get("variant_forms_raw")),
            "variant_forms": clean_list_text(row.get("variant_forms")),
            "pronunciations": build_rule_pronunciations(row, pos_columns),
            "part_of_speech": clean_pos(row.get(pos_col_name)),
            "definition": clean_text(row.get("definition")),
            "examples": clean_examples(row.get("examples")),
            "etymology": clean_text(row.get("etymology")),
            "cross_references": clean_cross_refs(row.get("cross_references")),
            "region_mentions": clean_region_values(row.get("region_mentions")),
            "needs_review": bool(row.get("needs_review", False)),
        }
        out_rows.append(record)
    out = pd.DataFrame(out_rows)
    return out[CORE_FIELDS].copy()


def normalize_genai(genai_df: pd.DataFrame) -> pd.DataFrame:
    """Normalise the flattened GenAI output into a canonical schema."""
    out_rows = []
    for _, row in genai_df.iterrows():
        record = {
            "entry_id": safe_int_from_id(row.get("entry_id")),
            "source_text": clean_text(row.get("source_text")),
            "headword_raw": clean_text(row.get("data.headword_raw")),
            "headword": clean_text(row.get("data.headword")),
            "variant_forms_raw": clean_text(row.get("data.variant_forms_raw")),
            "variant_forms": clean_list_text(row.get("data.variant_forms")),
            "pronunciations": clean_pronunciations(row.get("data.pronunciations")),
            "part_of_speech": clean_pos(row.get("data.part_of_speech")),
            "definition": clean_text(row.get("data.definition")),
            "examples": clean_examples(row.get("data.examples")),
            "etymology": clean_text(row.get("data.etymology")),
            "cross_references": clean_cross_refs(row.get("data.cross_references")),
            "region_mentions": clean_region_values(row.get("data.region_mentions")),
            "needs_review": bool(row.get("needs_review", False)),
        }
        out_rows.append(record)
    out = pd.DataFrame(out_rows)
    return out[CORE_FIELDS].copy()
