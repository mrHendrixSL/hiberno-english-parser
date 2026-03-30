"""Merging and comparison routines for parser outputs.

This module defines functions to align and compare the outputs of the
rule‑based and GenAI parsers. The primary function, :func:`merge_outputs`,
performs a full outer join on the integer ``entry_id`` and flags
potential misalignments based on the source text. Additional helpers
compute field presence/absence and exact match statistics.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..shared.utils import exact_text_match, exact_list_match, clean_list_text


COMPARE_FIELDS = [
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
]

TEXT_FIELDS = ["headword", "headword_raw", "definition", "etymology"]


def merge_outputs(rule_df: pd.DataFrame, genai_df: pd.DataFrame) -> pd.DataFrame:
    """Merge normalised rule and GenAI outputs on ``entry_id``.

    Performs a full outer join and appends a ``_merge`` indicator similar
    to :func:`pandas.merge`. Also computes an ``source_text_exact_match``
    flag indicating whether the source text is identical across sources.
    """
    merged = rule_df.merge(
        genai_df,
        on="entry_id",
        how="outer",
        suffixes=("_rule", "_genai"),
        indicator=True,
    )
    merged["source_text_exact_match"] = merged.apply(
        lambda r: exact_text_match(r.get("source_text_rule"), r.get("source_text_genai")),
        axis=1,
    )
    return merged


def presence_status(rule_value: Any, genai_value: Any) -> str:
    r = not pd.isna(rule_value) and rule_value not in (None, "", [], {})
    g = not pd.isna(genai_value) and genai_value not in (None, "", [], {})
    if r and g:
        return "both_present"
    if r and not g:
        return "rule_only"
    if not r and g:
        return "genai_only"
    return "both_missing"


def compute_presence_summary(merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field in COMPARE_FIELDS:
        status_col = f"{field}_presence_status"
        merged[status_col] = merged.apply(
            lambda r: presence_status(r.get(f"{field}_rule"), r.get(f"{field}_genai")),
            axis=1,
        )
        summary = merged[status_col].value_counts(dropna=False).to_dict()
        summary["field"] = field
        rows.append(summary)
    presence_summary = pd.DataFrame(rows).fillna(0)
    return presence_summary[["field", "both_present", "rule_only", "genai_only", "both_missing"]].sort_values("field")


def field_exact_match(field: str, row: pd.Series) -> bool:
    left = row.get(f"{field}_rule")
    right = row.get(f"{field}_genai")
    if field in TEXT_FIELDS:
        return exact_text_match(left, right)
    return exact_list_match(left, right)


def compute_exact_match_summary(merged: pd.DataFrame) -> pd.DataFrame:
    summary = []
    for field in COMPARE_FIELDS:
        merged[f"{field}_exact_match"] = merged.apply(lambda r, f=field: field_exact_match(f, r), axis=1)
        rate = merged[f"{field}_exact_match"].mean()
        summary.append({"field": field, "exact_match_rate": rate})
    return pd.DataFrame(summary).sort_values("exact_match_rate", ascending=False)
