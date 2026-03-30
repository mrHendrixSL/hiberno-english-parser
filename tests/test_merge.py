"""Tests for merging outputs."""

import pandas as pd

from hiberno_english_parser.src.evaluation.merge import merge_outputs


def test_merge_on_entry_id():
    rule_df = pd.DataFrame([
        {"entry_id": 1, "source_text": "rule", "headword": "r"},
        {"entry_id": 2, "source_text": "rule2", "headword": "r2"},
    ])
    genai_df = pd.DataFrame([
        {"entry_id": 1, "source_text": "rule", "headword": "r"},
        {"entry_id": 3, "source_text": "gen", "headword": "g"},
    ])
    merged = merge_outputs(rule_df, genai_df)
    assert len(merged) == 3
    assert merged["_merge"].value_counts().to_dict() == {"both": 1, "left_only": 1, "right_only": 1}