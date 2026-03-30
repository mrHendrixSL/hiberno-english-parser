"""Tests for normalisation functions."""

import pandas as pd

from hiberno_english_parser.src.evaluation.normalize import normalize_rule, normalize_genai


def test_normalize_rule():
    # minimal rule record
    rule_df = pd.DataFrame([
        {
            "entry_id": "1",
            "source_text": "craic /kræk/ n. fun, enjoyment.",
            "headword_raw": "craic",
            "headword": "craic",
            "variant_forms_raw": None,
            "variant_forms": None,
            "pronunciation": "kræk",
            "part_of_speech": "n.",
            "definition": "fun, enjoyment",
            "examples": [],
            "etymology": None,
            "cross_references": [],
            "region_mentions": [],
            "needs_review": False,
        }
    ])
    norm = normalize_rule(rule_df, ["pronunciation"], "part_of_speech")
    rec = norm.iloc[0]
    assert rec["headword"] == "craic"
    assert rec["pronunciations"] == ["kræk"]


def test_normalize_genai():
    genai_df = pd.DataFrame([
        {
            "entry_id": "1",
            "source_text": "craic /kræk/ n. fun, enjoyment.",
            "data.headword_raw": "craic",
            "data.headword": "craic",
            "data.variant_forms_raw": None,
            "data.variant_forms": None,
            "data.pronunciations": ["kræk"],
            "data.part_of_speech": ["n."],
            "data.definition": "fun, enjoyment",
            "data.examples": [],
            "data.etymology": None,
            "data.cross_references": [],
            "data.region_mentions": [],
            "needs_review": False,
        }
    ])
    norm = normalize_genai(genai_df)
    rec = norm.iloc[0]
    assert rec["pronunciations"] == ["kræk"]