"""
metrics.py
==========
Per-entry and aggregate evaluation metrics.

Provides both a pure-dict API (no pandas dependency) and a DataFrame API
for use in the full comparison pipeline.

Pure-dict API
-------------
  evaluate_entry(rb_rec, llm_rec)  → per-entry results dict
  aggregate(entry_results)         → corpus-level summary
  aggregate_by_stratum(…)          → per-stratum breakdown
  disagreement_examples(…)         → top-N worst disagreements per field

DataFrame API
-------------
  add_exact_match(df)
  add_token_similarity(df)
  add_field_presence(df)
  add_strata_flags(df)
  add_misclassification_flags(df)
  add_all_metrics(df)
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from difflib import SequenceMatcher

import pandas as pd

from src.shared.schema import CONTENT_FIELDS, STRATUM_COLS, MISCLASS_COLS
from src.shared.normalisation import (
    normalise,
    tokens,
    exact_match,
    ordered_similarity,
    unordered_similarity,
    to_flat_string,
)

# Structural characteristics used for per-stratum evaluation.
STRATA_CHECKS: dict = {
    "numbered_senses":     lambda r: isinstance(r.get("definition"), list),
    "who_adds":            lambda r: "who adds" in (r.get("full_text") or "").lower(),
    "multi_pronunciation": lambda r: r.get("pronunciation_2") is not None,
    "variant_forms":       lambda r: bool(r.get("variant_forms")),
    "with_etymology":      lambda r: bool(r.get("etymology")),
    "multi_region":        lambda r: len(r.get("region_mentions") or []) > 1,
    "long_definition":     lambda r: len(str(r.get("definition") or "")) > 120,
    "low_confidence":      lambda r: r.get("parse_confidence") == "low",
    "medium_confidence":   lambda r: r.get("parse_confidence") == "medium",
    "high_confidence":     lambda r: r.get("parse_confidence") == "high",
}

_ETYM_PAT = re.compile(r"<\s*(Ir|OE|ME|Fr|L\b|ON|Scots|Gael|E dial)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_null(val) -> bool:
    """True if value is None, NaN, or empty string."""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str) and val == "":
        return True
    return False


def _to_string(value) -> str:
    """Flatten any field value to a plain string (without full normalisation)."""
    return to_flat_string(value)


def _token_set(value) -> set[str]:
    return set(tokens(value))


# ---------------------------------------------------------------------------
# Hallucination detection
# ---------------------------------------------------------------------------

def _hallucination_flags(llm_rec: dict) -> dict[str, bool]:
    """Per-field flag: True if LLM output contains tokens not in full_text."""
    source_tokens = _token_set(llm_rec.get("full_text", ""))
    checked = ["definition", "etymology", "examples", "headword", "headword_raw", "variant_forms"]
    flags: dict[str, bool] = {}
    for f in checked:
        field_toks = _token_set(llm_rec.get(f))
        if not field_toks:
            flags[f] = False
        else:
            novel = {t for t in (field_toks - source_tokens) if len(t) > 3}
            flags[f] = len(novel) > 0
    return flags


# ---------------------------------------------------------------------------
# Pure-dict metric functions
# ---------------------------------------------------------------------------

def field_presence(rec: dict) -> dict[str, bool]:
    """Return per-field presence (non-null) flags."""
    return {f: rec.get(f) is not None for f in CONTENT_FIELDS}


def exact_agreement(rb_rec: dict, llm_rec: dict) -> dict[str, bool]:
    """Return per-field exact-match booleans (after normalisation)."""
    return {
        f: normalise(_to_string(rb_rec.get(f))) == normalise(_to_string(llm_rec.get(f)))
        for f in CONTENT_FIELDS
    }


def token_similarity(rb_rec: dict, llm_rec: dict) -> dict[str, dict]:
    """Return per-field ordered + unordered token similarity scores."""
    result: dict = {}
    for f in CONTENT_FIELDS:
        rb_toks  = tokens(rb_rec.get(f))
        llm_toks = tokens(llm_rec.get(f))

        if rb_toks or llm_toks:
            ordered = SequenceMatcher(None, rb_toks, llm_toks).ratio()
        else:
            ordered = 1.0

        rb_set  = set(rb_toks)
        llm_set = set(llm_toks)
        if rb_set or llm_set:
            precision = len(rb_set & llm_set) / len(llm_set) if llm_set else 0.0
            recall    = len(rb_set & llm_set) / len(rb_set)  if rb_set  else 0.0
            f1        = (2 * precision * recall / (precision + recall)
                         if (precision + recall) > 0 else 0.0)
        else:
            f1 = 1.0

        result[f] = {"ordered": round(ordered, 4), "unordered": round(f1, 4)}
    return result


def source_coverage(rec: dict) -> dict:
    """Extract pre-computed coverage fields from a record."""
    return {
        "coverage_pct":       rec.get("coverage_pct"),
        "coverage_char_pct":  rec.get("coverage_char_pct"),
        "coverage_uncovered": rec.get("coverage_uncovered"),
    }


def evaluate_entry(rb_rec: dict, llm_rec: dict) -> dict:
    """Compute all metrics for a single aligned (rb, llm) pair."""
    return {
        "para_id":         rb_rec["para_id"],
        "headword":        rb_rec.get("headword"),
        "field_presence":  {
            "rule_based": field_presence(rb_rec),
            "llm":        field_presence(llm_rec),
        },
        "exact_agreement":     exact_agreement(rb_rec, llm_rec),
        "token_similarity":    token_similarity(rb_rec, llm_rec),
        "source_coverage": {
            "rule_based": source_coverage(rb_rec),
            "llm":        source_coverage(llm_rec),
        },
        "hallucination_flags": _hallucination_flags(llm_rec),
        "strata":              {k: fn(rb_rec) for k, fn in STRATA_CHECKS.items()},
    }


# ---------------------------------------------------------------------------
# Aggregate functions
# ---------------------------------------------------------------------------

def _mean(lst: list) -> float | None:
    return round(sum(lst) / len(lst), 2) if lst else None


def aggregate(entry_results: list) -> dict:
    """Roll up entry-level metrics to corpus-level summary."""
    n = len(entry_results)
    if n == 0:
        return {}

    exact_counts  = defaultdict(int)
    tok_ordered   = defaultdict(float)
    tok_unordered = defaultdict(float)
    rb_present    = defaultdict(int)
    llm_present   = defaultdict(int)
    rb_cov_pct:  list = []
    llm_cov_pct: list = []
    rb_cov_char: list = []
    llm_cov_char:list = []
    halluc_counts = defaultdict(int)

    for er in entry_results:
        for f, v in er["exact_agreement"].items():
            if v:
                exact_counts[f] += 1
        for f, scores in er["token_similarity"].items():
            tok_ordered[f]   += scores["ordered"]
            tok_unordered[f] += scores["unordered"]
        for f, v in er["field_presence"]["rule_based"].items():
            if v:
                rb_present[f] += 1
        for f, v in er["field_presence"]["llm"].items():
            if v:
                llm_present[f] += 1
        rb_c  = er["source_coverage"]["rule_based"]
        llm_c = er["source_coverage"]["llm"]
        if rb_c["coverage_pct"] is not None:
            rb_cov_pct.append(rb_c["coverage_pct"])
        if llm_c["coverage_pct"] is not None:
            llm_cov_pct.append(llm_c["coverage_pct"])
        if rb_c["coverage_char_pct"] is not None:
            rb_cov_char.append(rb_c["coverage_char_pct"])
        if llm_c["coverage_char_pct"] is not None:
            llm_cov_char.append(llm_c["coverage_char_pct"])
        for f, v in er.get("hallucination_flags", {}).items():
            if v:
                halluc_counts[f] += 1

    return {
        "n": n,
        "exact_agreement_pct": {
            f: round(100 * exact_counts[f] / n, 1) for f in CONTENT_FIELDS
        },
        "mean_token_similarity": {
            f: {
                "ordered":   round(tok_ordered[f] / n, 4),
                "unordered": round(tok_unordered[f] / n, 4),
            }
            for f in CONTENT_FIELDS
        },
        "mean_coverage": {
            "rule_based": {
                "coverage_pct":      _mean(rb_cov_pct),
                "coverage_char_pct": _mean(rb_cov_char),
            },
            "llm": {
                "coverage_pct":      _mean(llm_cov_pct),
                "coverage_char_pct": _mean(llm_cov_char),
            },
        },
        "field_population_pct": {
            "rule_based": {f: round(100 * rb_present[f] / n, 1) for f in CONTENT_FIELDS},
            "llm":        {f: round(100 * llm_present[f] / n, 1) for f in CONTENT_FIELDS},
        },
        "hallucination_pct": {
            f: round(100 * halluc_counts[f] / n, 1) for f in halluc_counts
        },
    }


def aggregate_by_stratum(entry_results: list) -> dict:
    """Compute aggregate metrics broken down by structural stratum."""
    stratum_results: dict = defaultdict(list)
    for er in entry_results:
        for stratum, present in er.get("strata", {}).items():
            if present:
                stratum_results[stratum].append(er)
    return {
        stratum: aggregate(ers)
        for stratum, ers in stratum_results.items()
        if ers
    }


def disagreement_examples(
    entry_results: list,
    rb_index: dict,
    llm_index: dict,
    top_n: int = 5,
) -> dict:
    """For each field, return the top_n entries where RB and LLM disagree most."""
    field_scores: dict = defaultdict(list)
    for er in entry_results:
        for f in CONTENT_FIELDS:
            score = er["token_similarity"][f]["ordered"]
            if not er["exact_agreement"][f]:
                field_scores[f].append((er["para_id"], er["headword"], score))

    examples: dict = {}
    for f, scores in field_scores.items():
        worst = sorted(scores, key=lambda x: x[2])[:top_n]
        examples[f] = []
        for para_id, headword, score in worst:
            rb_rec  = rb_index.get(para_id, {})
            llm_rec = llm_index.get(para_id, {})
            examples[f].append({
                "para_id":    para_id,
                "headword":   headword,
                "similarity": score,
                "full_text":  rb_rec.get("full_text", ""),
                "rule_based": rb_rec.get(f),
                "llm":        llm_rec.get(f),
            })

    return examples


# ---------------------------------------------------------------------------
# Full evaluation runner (pure-dict)
# ---------------------------------------------------------------------------

def run_evaluation(
    rb_records: list,
    llm_records: list,
    output_path: str | None = None,
    top_n_examples: int = 5,
) -> dict:
    """Run full evaluation and optionally write to *output_path*."""
    from src.shared.io_utils import save_json

    rb_index  = {r["para_id"]: r for r in rb_records}
    llm_index = {r["para_id"]: r for r in llm_records}

    common_ids = sorted(set(rb_index) & set(llm_index))
    print(f"Evaluating {len(common_ids)} aligned entries "
          f"(rb={len(rb_index)}, llm={len(llm_index)})")

    entry_results = [
        evaluate_entry(rb_index[pid], llm_index[pid])
        for pid in common_ids
    ]

    output = {
        "summary":               aggregate(entry_results),
        "stratum_summary":       aggregate_by_stratum(entry_results),
        "entry_results":         entry_results,
        "disagreement_examples": disagreement_examples(
            entry_results, rb_index, llm_index, top_n=top_n_examples
        ),
    }

    if output_path:
        save_json(output_path, output)
        print(f"Evaluation saved → {output_path}")

    return output


# ---------------------------------------------------------------------------
# DataFrame API
# ---------------------------------------------------------------------------

def add_exact_match(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``{field}_exact_match`` boolean columns."""
    df = df.copy()
    for field in CONTENT_FIELDS:
        rb_vals  = df[f"{field}_Rule"].values
        llm_vals = df[f"{field}_LLM"].values
        df[f"{field}_exact_match"] = [exact_match(a, b) for a, b in zip(rb_vals, llm_vals)]
    return df


def add_token_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``{field}_ordered_sim`` and ``{field}_unordered_sim`` columns."""
    df = df.copy()
    for field in CONTENT_FIELDS:
        rb_vals  = df[f"{field}_Rule"].values
        llm_vals = df[f"{field}_LLM"].values
        df[f"{field}_ordered_sim"]   = [ordered_similarity(a, b)   for a, b in zip(rb_vals, llm_vals)]
        df[f"{field}_unordered_sim"] = [unordered_similarity(a, b) for a, b in zip(rb_vals, llm_vals)]
    return df


def add_field_presence(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``{field}_present_Rule`` and ``{field}_present_LLM`` boolean columns."""
    df = df.copy()
    for field in CONTENT_FIELDS:
        df[f"{field}_present_Rule"] = [not _is_null(v) for v in df[f"{field}_Rule"].values]
        df[f"{field}_present_LLM"]  = [not _is_null(v) for v in df[f"{field}_LLM"].values]
    return df


def add_strata_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``stratum_*`` boolean columns using rule-based values."""
    df = df.copy()

    # Confidence comes from the rule-based parse_confidence field stored in
    # the merged DataFrame.  The RB output must have been merged in with a
    # parse_confidence_Rule column; fall back to an empty map if absent.
    parse_confidence_col = "parse_confidence_Rule"
    conf_map: dict = {}
    if parse_confidence_col in df.columns:
        conf_map = dict(zip(df["para_id"].values, df[parse_confidence_col].values))

    para_ids = df["para_id"].values
    df["stratum_high_confidence"]   = [conf_map.get(pid) == "high"   for pid in para_ids]
    df["stratum_medium_confidence"] = [conf_map.get(pid) == "medium" for pid in para_ids]
    df["stratum_low_confidence"]    = [conf_map.get(pid) == "low"    for pid in para_ids]

    df["stratum_numbered_senses"]   = [isinstance(v, list) for v in df["definition_Rule"].values]
    df["stratum_who_adds"]          = [
        "who adds" in (str(t).lower() if t else "") for t in df["full_text"].values
    ]
    df["stratum_multi_pronunciation"] = [not _is_null(v) for v in df["pronunciation_2_Rule"].values]
    df["stratum_variant_forms"]       = [not _is_null(v) for v in df["variant_forms_Rule"].values]
    df["stratum_with_etymology"]      = [not _is_null(v) for v in df["etymology_Rule"].values]
    df["stratum_multi_region"]        = [
        isinstance(v, list) and len(v) > 1 for v in df["region_mentions_Rule"].values
    ]
    df["stratum_long_definition"]     = [
        len(str(v or "")) > 120 for v in df["definition_Rule"].values
    ]
    return df


def add_misclassification_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``misclass_*`` boolean columns."""
    df = df.copy()

    def_llm       = df["definition_LLM"].values
    def_rule      = df["definition_Rule"].values
    examples_rule = df["examples_Rule"].values
    examples_llm  = df["examples_LLM"].values
    etym_rule     = df["etymology_Rule"].values
    etym_llm      = df["etymology_LLM"].values
    xref_rule     = df["cross_references_Rule"].values
    xref_llm      = df["cross_references_LLM"].values

    etym_in_def       = [bool(_ETYM_PAT.search(str(v or ""))) for v in def_llm]
    examples_in_def   = [
        "'" in str(v or "") and not _is_null(er)
        for v, er in zip(def_llm, examples_rule)
    ]
    chained_etym      = [
        str(er or "").count("<") > 1 and str(el or "").count("<") == 1
        for er, el in zip(etym_rule, etym_llm)
    ]
    examples_dropped  = [
        not _is_null(er) and _is_null(el)
        for er, el in zip(examples_rule, examples_llm)
    ]
    numbered_not_split = [
        isinstance(dr, list) and isinstance(dl, str)
        for dr, dl in zip(def_rule, def_llm)
    ]
    cross_ref_missed  = [
        not _is_null(xr) and _is_null(xl)
        for xr, xl in zip(xref_rule, xref_llm)
    ]
    any_flag = [
        any([e, ei, c, ed, ns, cr])
        for e, ei, c, ed, ns, cr in zip(
            etym_in_def, examples_in_def, chained_etym,
            examples_dropped, numbered_not_split, cross_ref_missed,
        )
    ]

    df["misclass_etym_in_definition"]       = etym_in_def
    df["misclass_examples_in_definition"]   = examples_in_def
    df["misclass_chained_etym_collapsed"]   = chained_etym
    df["misclass_examples_dropped"]         = examples_dropped
    df["misclass_numbered_senses_not_split"] = numbered_not_split
    df["misclass_cross_ref_missed"]         = cross_ref_missed
    df["misclass_any"]                      = any_flag
    return df


def add_all_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all DataFrame metric functions in order."""
    df = add_exact_match(df)
    df = add_token_similarity(df)
    df = add_field_presence(df)
    df = add_strata_flags(df)
    df = add_misclassification_flags(df)
    return df
