"""
tests/test_parser.py
====================
Smoke tests for the rule-based parser.

Run with: pytest tests/test_parser.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rule_based.parser import parse_entry, check_coverage


# ---------------------------------------------------------------------------
# Sample entries drawn from the few-shot examples in the system prompt
# ---------------------------------------------------------------------------

SAMPLE_ENTRIES = {
    "standard_full": {
        "para_id": 1,
        "text": (
            "ABCs /eːbiːsiːz/ n. (colloq.), irregular red lines on children's and "
            "women's shins caused by sitting too close to open fires (JOM, Kerry). "
            "See BRACKEN."
        ),
        "expect": {
            "headword":          "abcs",
            "headword_raw":      "ABCs",
            "pronunciation":     "eːbiːsiːz",
            "part_of_speech":    "n",
            "grammatical_labels":"colloq.",
            "entry_type":        "full",
        },
    },
    "etymology_examples": {
        "para_id": 2,
        "text": (
            "abhaile /əˈwɑljə/ adv., home, homewards < Ir. "
            "'SLÁN abhaile,' safe home."
        ),
        "expect": {
            "headword":       "abhaile",
            "pronunciation":  "əˈwɑljə",
            "part_of_speech": "adv",
            "entry_type":     "full",
        },
    },
    "cross_ref": {
        "para_id": 3,
        "text": "a chora, see A CHARA.",
        "expect": {
            "entry_type":       "cross_ref",
            "cross_references": ["A CHARA"],
        },
    },
    "section_header": {
        "para_id": 4,
        "text": "A",
        "expect": {
            "entry_type":       "header",
            "parse_confidence": "skip",
        },
    },
    "variant_forms": {
        "para_id": 5,
        "text": (
            "ach /ɑx/ also och interj., with a hint of sadness (SOM, Kerry) "
            "or disgust < Ir. 'Ach, don't vex me.'"
        ),
        "expect": {
            "headword":    "ach",
            "entry_type":  "full",
        },
    },
}


def _parse(key: str) -> dict:
    entry = SAMPLE_ENTRIES[key]
    return parse_entry(entry["para_id"], entry["text"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_standard_full_entry():
    rec = _parse("standard_full")
    exp = SAMPLE_ENTRIES["standard_full"]["expect"]
    for field, val in exp.items():
        assert rec.get(field) == val, f"Field '{field}': expected {val!r}, got {rec.get(field)!r}"


def test_etymology_and_examples():
    rec = _parse("etymology_examples")
    exp = SAMPLE_ENTRIES["etymology_examples"]["expect"]
    for field, val in exp.items():
        assert rec.get(field) == val
    assert rec.get("etymology") is not None, "Etymology should be extracted"
    assert rec.get("examples") is not None, "Examples should be extracted"


def test_cross_ref_entry():
    rec = _parse("cross_ref")
    assert rec["entry_type"] == "cross_ref"
    assert rec["cross_references"] == ["A CHARA"]
    assert rec.get("definition") is None


def test_section_header():
    rec = _parse("section_header")
    assert rec["entry_type"]       == "header"
    assert rec["parse_confidence"] == "skip"


def test_variant_forms_extracted():
    rec = _parse("variant_forms")
    assert rec["headword"] == "ach"
    assert rec.get("variant_forms") is not None, "variant_forms should be populated"
    assert "och" in rec.get("variant_forms", [])


def test_region_mentions_extracted():
    rec = _parse("standard_full")
    regions = rec.get("region_mentions") or []
    assert any(r["informant"] == "JOM" for r in regions), "JOM informant should appear"
    assert any(r["county"] == "Kerry"  for r in regions), "Kerry county should appear"


def test_cross_references_extracted():
    rec = _parse("standard_full")
    assert rec.get("cross_references") is not None
    assert "BRACKEN" in (rec.get("cross_references") or [])


def test_coverage_non_null():
    """Coverage should be computed for all non-header entries."""
    for key in ("standard_full", "etymology_examples", "cross_ref", "variant_forms"):
        rec = _parse(key)
        assert rec.get("coverage_pct") is not None, f"{key}: coverage_pct should not be None"


def test_check_coverage_empty_text():
    """check_coverage should handle empty full_text gracefully."""
    result = check_coverage({"full_text": ""})
    assert result["covered_pct"] is None
    assert result["coverage_char_pct"] is None
    assert result["uncovered"] == []


def test_no_pronunciation_entry():
    """Entries without pronunciation should receive low/medium confidence."""
    rec = parse_entry(99, "bloog n.phr., some kind of thing.")
    assert rec["parse_confidence"] in ("low", "medium")
    assert rec.get("headword") is not None


def test_numbered_senses():
    rec = parse_entry(
        100,
        "ábhar /ˈɔːvər/ n. 1. Appreciable quantity < Ir. 'He brought a great ábhar.' "
        "2. Swelling, cyst (SOM, Kerry).",
    )
    assert rec["entry_type"] == "full"
    defn = rec.get("definition")
    assert isinstance(defn, list), f"Numbered senses should produce a list, got {type(defn)}"
    assert len(defn) >= 2
