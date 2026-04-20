"""
aggregation.py
==============
Compute aggregate statistics and per-stratum breakdowns from a metrics
DataFrame produced by the evaluation pipeline.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.shared.schema import CONTENT_FIELDS, STRATUM_COLS, MISCLASS_COLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_python(val):
    """Convert numpy/pandas scalar types to native Python for JSON serialisation."""
    if val is None or val is pd.NA:
        return None
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return None if math.isnan(val) else float(val)
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def _bool_mean(series) -> float:
    """Mean of a boolean-like series, ignoring None/NaN."""
    vals = [
        v for v in series
        if v is not None and v is not pd.NA
        and not (isinstance(v, float) and math.isnan(v))
    ]
    return sum(1 for v in vals if v) / len(vals) if vals else 0.0


def _float_mean(series) -> float:
    """Mean of a float-like series, ignoring None/NaN."""
    vals = [
        float(v) for v in series
        if v is not None and v is not pd.NA
        and not (isinstance(v, float) and math.isnan(v))
    ]
    return sum(vals) / len(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# Aggregate stats
# ---------------------------------------------------------------------------

def compute_aggregate(df: pd.DataFrame) -> dict:
    """Compute corpus-level aggregate statistics from the metrics DataFrame."""
    n = len(df)

    exact_agreement_pct: dict = {
        field: round(100 * _bool_mean(df[f"{field}_exact_match"]), 1)
        for field in CONTENT_FIELDS
    }

    token_similarity: dict = {
        field: {
            "ordered":   round(_float_mean(df[f"{field}_ordered_sim"]),   4),
            "unordered": round(_float_mean(df[f"{field}_unordered_sim"]), 4),
        }
        for field in CONTENT_FIELDS
    }

    field_presence: dict = {}
    for field in CONTENT_FIELDS:
        rb_true  = [bool(v) if v is not None else False for v in df[f"{field}_present_Rule"]]
        llm_true = [bool(v) if v is not None else False for v in df[f"{field}_present_LLM"]]
        field_presence[field] = {
            "rb_pct":   round(100 * sum(rb_true) / n, 1),
            "llm_pct":  round(100 * sum(llm_true) / n, 1),
            "both":     sum(1 for r, l in zip(rb_true, llm_true) if r and l),
            "neither":  sum(1 for r, l in zip(rb_true, llm_true) if not r and not l),
            "rb_only":  sum(1 for r, l in zip(rb_true, llm_true) if r and not l),
            "llm_only": sum(1 for r, l in zip(rb_true, llm_true) if not r and l),
        }

    coverage = {
        "mean_rb_coverage_pct":  round(float(df["coverage_pct_Rule"].mean()),      2),
        "mean_llm_coverage_pct": round(float(df["coverage_pct_LLM"].mean()),       2),
        "mean_rb_char_pct":      round(float(df["coverage_char_pct_Rule"].mean()), 2),
        "mean_llm_char_pct":     round(float(df["coverage_char_pct_LLM"].mean()),  2),
        "llm_below_80_count":    int((df["coverage_pct_LLM"] < 80).sum()),
    }

    misclassification_counts: dict = {
        col: int(sum(1 for v in df[col] if v is True))
        for col in MISCLASS_COLS
    }

    return {
        "n":                      n,
        "exact_agreement_pct":    exact_agreement_pct,
        "token_similarity":       token_similarity,
        "field_presence":         field_presence,
        "coverage":               coverage,
        "misclassification_counts": misclassification_counts,
    }


def compute_stratum_agreement(df: pd.DataFrame) -> dict:
    """Compute per-stratum exact-agreement and token-similarity breakdowns."""
    result: dict = {}
    for stratum in STRATUM_COLS:
        subset = df[[bool(v) for v in df[stratum]]]
        n      = len(subset)
        exact_pct: dict = {
            f: round(100 * _bool_mean(subset[f"{f}_exact_match"]), 1)
            for f in CONTENT_FIELDS
        }
        mean_tok: dict = {
            f: {
                "ordered":   round(_float_mean(subset[f"{f}_ordered_sim"]),   4),
                "unordered": round(_float_mean(subset[f"{f}_unordered_sim"]), 4),
            }
            for f in CONTENT_FIELDS
        }
        result[stratum] = {
            "n":                    n,
            "exact_agreement_pct":  exact_pct,
            "mean_token_similarity": mean_tok,
        }
    return result


def build_entry_records(df: pd.DataFrame) -> list:
    """Build per-entry comparison records for JSON output."""
    records: list = []
    for _, row in df.iterrows():
        rb  = {f: _to_python(row[f"{f}_Rule"]) for f in CONTENT_FIELDS}
        llm = {f: _to_python(row[f"{f}_LLM"])  for f in CONTENT_FIELDS}

        exact_agr = {f: _to_python(row[f"{f}_exact_match"]) for f in CONTENT_FIELDS}
        tok_sim   = {
            f: {
                "ordered":   _to_python(row[f"{f}_ordered_sim"]),
                "unordered": _to_python(row[f"{f}_unordered_sim"]),
            }
            for f in CONTENT_FIELDS
        }
        exact_vals = [v for v in exact_agr.values() if v is not None]
        agree_pct  = (
            round(100 * sum(1 for v in exact_vals if v) / len(exact_vals), 1)
            if exact_vals else 0.0
        )

        records.append({
            "para_id":   int(row["para_id"]),
            "full_text": str(row["full_text"] or ""),
            "rb":        rb,
            "llm":       llm,
            "comparison": {
                "agree_pct":       agree_pct,
                "exact_agreement": exact_agr,
                "token_similarity":tok_sim,
                "rb_coverage_pct": _to_python(row["coverage_pct_Rule"]),
                "llm_coverage_pct":_to_python(row["coverage_pct_LLM"]),
                "misclassification_flags": {
                    col: _to_python(row[col])
                    for col in MISCLASS_COLS if col != "misclass_any"
                },
                "strata": {s: _to_python(row[s]) for s in STRATUM_COLS},
                "any_misclassification": _to_python(row["misclass_any"]),
            },
        })

    records.sort(key=lambda r: r["para_id"])
    return records
