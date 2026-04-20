"""
tests/test_normalisation.py
===========================
Tests for src.shared.normalisation

Run with: pytest tests/test_normalisation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.normalisation import (
    normalise_fullwidth,
    to_flat_string,
    normalise,
    tokens,
    exact_match,
    ordered_similarity,
    unordered_similarity,
    COVERAGE_STOPWORDS,
)


# ---------------------------------------------------------------------------
# normalise_fullwidth
# ---------------------------------------------------------------------------

def test_fullwidth_ascii_roundtrip():
    """Fullwidth Latin chars should map to ASCII."""
    assert normalise_fullwidth("ｄ") == "d"
    assert normalise_fullwidth("ｔ") == "t"
    assert normalise_fullwidth("ａｂｃ") == "abc"


def test_fullwidth_preserves_normal_chars():
    assert normalise_fullwidth("abc") == "abc"
    assert normalise_fullwidth("əˈwɑljə") == "əˈwɑljə"  # IPA unchanged
    assert normalise_fullwidth("") == ""


def test_fullwidth_none_safe():
    """Should not crash on empty / falsy input."""
    assert normalise_fullwidth("") == ""


# ---------------------------------------------------------------------------
# to_flat_string
# ---------------------------------------------------------------------------

def test_to_flat_string_none():
    assert to_flat_string(None) == ""


def test_to_flat_string_list_of_strings():
    result = to_flat_string(["apple", "banana"])
    assert "apple" in result
    assert "banana" in result


def test_to_flat_string_list_of_dicts():
    region = [{"informant": "SOM", "county": "Kerry"}]
    result = to_flat_string(region)
    assert "SOM" in result
    assert "Kerry" in result


def test_to_flat_string_dict():
    result = to_flat_string({"key": "value"})
    assert "value" in result


def test_to_flat_string_float_nan():
    import math
    assert to_flat_string(float("nan")) == ""


def test_to_flat_string_integer_float():
    assert to_flat_string(3.0) == "3"


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------

def test_normalise_strips_diacritics():
    result = normalise("ábhar")
    assert "a" in result
    assert "b" in result


def test_normalise_lowercases():
    assert normalise("HELLO") == "hello"


def test_normalise_fullwidth_in_pipeline():
    assert normalise("ｄog") == "dog"


def test_normalise_empty():
    assert normalise(None) == ""
    assert normalise("") == ""


# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------

def test_tokens_basic():
    result = tokens("the quick brown fox")
    assert "quick" in result
    assert "brown" in result


def test_tokens_none():
    assert tokens(None) == []


# ---------------------------------------------------------------------------
# exact_match
# ---------------------------------------------------------------------------

def test_exact_match_identical():
    assert exact_match("hello", "hello") is True


def test_exact_match_diacritic_insensitive():
    assert exact_match("ábhar", "abhar") is True


def test_exact_match_case_insensitive():
    assert exact_match("Kerry", "kerry") is True


def test_exact_match_different():
    assert exact_match("apple", "orange") is False


def test_exact_match_none_none():
    assert exact_match(None, None) is True


def test_exact_match_none_vs_value():
    assert exact_match(None, "something") is False


# ---------------------------------------------------------------------------
# ordered_similarity
# ---------------------------------------------------------------------------

def test_ordered_sim_identical():
    assert ordered_similarity("the quick fox", "the quick fox") == 1.0


def test_ordered_sim_both_empty():
    assert ordered_similarity(None, None) == 1.0


def test_ordered_sim_one_empty():
    assert ordered_similarity("something", None) == 0.0


def test_ordered_sim_range():
    score = ordered_similarity("the quick fox", "the slow dog")
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# unordered_similarity
# ---------------------------------------------------------------------------

def test_unordered_sim_identical():
    assert unordered_similarity("apple banana", "apple banana") == 1.0


def test_unordered_sim_reorder():
    s1 = unordered_similarity("apple banana", "banana apple")
    assert s1 == 1.0


def test_unordered_sim_both_empty():
    assert unordered_similarity(None, None) == 1.0


def test_unordered_sim_one_empty():
    assert unordered_similarity("something", None) == 0.0


# ---------------------------------------------------------------------------
# COVERAGE_STOPWORDS
# ---------------------------------------------------------------------------

def test_stopwords_is_frozenset():
    assert isinstance(COVERAGE_STOPWORDS, frozenset)


def test_stopwords_contains_expected():
    for word in ("see", "also", "the", "and", "ir", "oe"):
        assert word in COVERAGE_STOPWORDS, f"'{word}' should be in COVERAGE_STOPWORDS"
