"""
tests/test_evaluation.py
========================
Tests for the evaluation metrics module.

Run with: pytest tests/test_evaluation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.metrics import (
    field_presence,
    exact_agreement,
    token_similarity,
    evaluate_entry,
    aggregate,
)
from src.evaluation.preprocessing import _extract_homonym_index


# ---------------------------------------------------------------------------
# Minimal test records
# ---------------------------------------------------------------------------

RB_REC = {
    "para_id":       1,
    "full_text":     "ABCs /eːbiːsiːz/ n. (colloq.), irregular red lines. See BRACKEN.",
    "entry_type":    "full",
    "headword":      "abcs",
    "headword_raw":  "ABCs",
    "homonym_index": None,
    "variant_forms": None,
    "pronunciation": "eːbiːsiːz",
    "pronunciation_2": None,
    "pronunciation_3": None,
    "part_of_speech":    "n",
    "grammatical_labels":"colloq.",
    "definition":    "irregular red lines on children's shins",
    "etymology":     None,
    "cross_references": ["BRACKEN"],
    "examples":      None,
    "region_mentions": [{"informant": "JOM", "county": "Kerry"}],
    "parse_confidence": "high",
    "coverage_pct":     90.0,
    "coverage_char_pct":85.0,
    "coverage_uncovered": None,
}

LLM_REC = dict(RB_REC)  # identical — all metrics should be perfect


# ---------------------------------------------------------------------------
# field_presence
# ---------------------------------------------------------------------------

def test_field_presence_non_null():
    presence = field_presence(RB_REC)
    assert presence["headword"] is True
    assert presence["pronunciation"] is True
    assert presence["etymology"] is False  # None in RB_REC


def test_field_presence_null():
    presence = field_presence({"para_id": 1, "headword": None})
    assert presence["headword"] is False


# ---------------------------------------------------------------------------
# exact_agreement
# ---------------------------------------------------------------------------

def test_exact_agreement_identical():
    agr = exact_agreement(RB_REC, LLM_REC)
    for field, val in agr.items():
        assert val is True, f"Field '{field}' should agree when records are identical"


def test_exact_agreement_different_definition():
    llm = dict(LLM_REC, definition="different definition text here")
    agr = exact_agreement(RB_REC, llm)
    assert agr["definition"] is False
    assert agr["headword"] is True  # other fields still agree


def test_exact_agreement_none_vs_none():
    agr = exact_agreement(
        {"para_id": 1, "etymology": None},
        {"para_id": 1, "etymology": None},
    )
    assert agr["etymology"] is True


# ---------------------------------------------------------------------------
# token_similarity
# ---------------------------------------------------------------------------

def test_token_similarity_identical():
    sim = token_similarity(RB_REC, LLM_REC)
    for f, scores in sim.items():
        assert scores["ordered"] == 1.0, f"{f} ordered sim should be 1.0 for identical records"
        assert scores["unordered"] == 1.0


def test_token_similarity_both_null():
    sim = token_similarity(
        {"para_id": 1, "etymology": None},
        {"para_id": 1, "etymology": None},
    )
    assert sim["etymology"]["ordered"] == 1.0


def test_token_similarity_range():
    llm = dict(LLM_REC, definition="completely different words here altogether")
    sim = token_similarity(RB_REC, llm)
    score = sim["definition"]["ordered"]
    assert 0.0 <= score < 1.0


# ---------------------------------------------------------------------------
# evaluate_entry
# ---------------------------------------------------------------------------

def test_evaluate_entry_structure():
    result = evaluate_entry(RB_REC, LLM_REC)
    assert result["para_id"] == 1
    assert "field_presence" in result
    assert "exact_agreement" in result
    assert "token_similarity" in result
    assert "source_coverage" in result
    assert "hallucination_flags" in result
    assert "strata" in result


def test_evaluate_entry_strata():
    result = evaluate_entry(RB_REC, LLM_REC)
    assert result["strata"]["high_confidence"] is True
    assert result["strata"]["numbered_senses"] is False


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def test_aggregate_single_entry():
    er = evaluate_entry(RB_REC, LLM_REC)
    agg = aggregate([er])
    assert agg["n"] == 1
    # All fields should have 100% agreement since records are identical
    for field, pct in agg["exact_agreement_pct"].items():
        assert pct == 100.0, f"{field}: expected 100%, got {pct}%"


def test_aggregate_empty():
    agg = aggregate([])
    assert agg == {}


# ---------------------------------------------------------------------------
# _extract_homonym_index
# ---------------------------------------------------------------------------

def test_extract_homonym_index_strips_digit():
    records = [{"headword": "bac1", "homonym_index": None}]
    result  = _extract_homonym_index(records)
    assert result[0]["headword"]      == "bac"
    assert result[0]["homonym_index"] == 1


def test_extract_homonym_index_no_digit():
    records = [{"headword": "abhaile", "homonym_index": None}]
    result  = _extract_homonym_index(records)
    assert result[0]["headword"]      == "abhaile"
    assert result[0]["homonym_index"] is None
