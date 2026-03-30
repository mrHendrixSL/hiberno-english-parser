"""Unit tests for the rule‑based parser."""

from hiberno_english_parser.src.rule_based.parser import parse_entry


def test_simple_noun_entry():
    text = "craic /kræk/ n. fun, enjoyment."
    rec = parse_entry(text, 1)
    assert rec["headword"] == "craic"
    assert rec["pronunciation"] == "kræk"
    assert rec["part_of_speech"] == "n."
    assert rec["entry_type"] == "lexical"