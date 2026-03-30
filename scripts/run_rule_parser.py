#!/usr/bin/env python
"""Entry point for running the rule‑based parser.

This script reads a Word document containing dictionary entries, applies
the rule‑based parser to each paragraph and writes the structured
results to disk. Configuration is provided via a YAML file (see
``configs/rule_parser_config.yaml``) and allows the caller to specify
input/output locations. The script intentionally avoids any hard‑coded
paths or environment assumptions.
"""

from __future__ import annotations

import json
from pathlib import Path
import os
import sys
import argparse
import pandas as pd

# Extend sys.path to include the local ``src`` directory. This allows
# importing the internal packages (shared, rule_based, genai, evaluation)
# without requiring the project to be installed as a site‑package. The
# ``src`` directory lives alongside this ``scripts`` folder.
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_PATH = BASE_DIR / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from shared.config import load_config  # type: ignore
from rule_based.docx_reader import extract_paragraphs  # type: ignore
from rule_based.parser import parse_entries  # type: ignore


def build_audit_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute simple quality flags for each paragraph.

    The audit includes character counts, word counts and heuristic flags
    to identify potential headings or empty paragraphs. Additional
    features can be added here as needed.
    """
    audit = df.copy()
    audit["char_count"] = audit["text"].str.len()
    audit["word_count"] = audit["text"].str.split().str.len()
    audit["starts_with"] = audit["text"].str[:20]
    audit["ends_with"] = audit["text"].str[-20:]
    audit["has_digit"] = audit["text"].str.contains(r"\d", regex=True)
    audit["has_brackets"] = audit["text"].str.contains(r"[\[\]\(\)]", regex=True)
    audit["has_slash"] = audit["text"].str.contains("/", regex=False)
    audit["has_semicolon"] = audit["text"].str.contains(";", regex=False)
    audit["has_colon"] = audit["text"].str.contains(":", regex=False)
    audit["has_quote"] = audit["text"].str.contains(r"[\"'“”‘’]", regex=True)
    audit["flag_short"] = audit["char_count"] < 25
    audit["flag_long"] = audit["char_count"] > 1200
    audit["flag_low_word_count"] = audit["word_count"] <= 3
    audit["flag_possible_heading"] = (audit["word_count"] <= 6) & (~audit["text"].str.contains(r"[.;:!?]", regex=True))
    audit["flag_single_letter_header"] = audit["text"].str.strip().str.fullmatch(r"[A-Z]")
    audit["flag_all_caps_short"] = (
        audit["text"].str.fullmatch(r"[A-Z&\- ]{1,8}") & (audit["word_count"] <= 2)
    ).fillna(False)
    flag_cols = [
        "flag_short",
        "flag_long",
        "flag_low_word_count",
        "flag_possible_heading",
        "flag_single_letter_header",
        "flag_all_caps_short",
    ]
    audit["needs_review"] = audit[flag_cols].any(axis=1)
    return audit


def run_rule_parser(config_path: str | Path) -> None:
    config = load_config(config_path)
    # resolve paths relative to the config file
    cfg_dir = Path(config_path).resolve().parent
    input_docx = Path(cfg_dir, config.input_docx).resolve()
    output_jsonl = Path(cfg_dir, config.output_jsonl).resolve()
    output_csv = None if config.get("output_csv") in (None, "", "null") else Path(cfg_dir, config.output_csv).resolve()
    write_audit = bool(config.get("write_audit", False))
    audit_csv = None
    if write_audit:
        audit_csv = Path(cfg_dir, config.audit_csv).resolve()
    # ensure output directories exist
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if output_csv:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
    if audit_csv:
        audit_csv.parent.mkdir(parents=True, exist_ok=True)
    # extract paragraphs
    paragraphs_df = extract_paragraphs(input_docx)
    # optionally write audit
    if write_audit and audit_csv:
        audit_df = build_audit_df(paragraphs_df)
        audit_df.to_csv(audit_csv, index=False)
    # parse entries
    records = parse_entries(paragraphs_df["text"].tolist())
    df = pd.DataFrame(records)
    # write JSONL
    with output_jsonl.open("w", encoding="utf-8") as f:
        for record in df.to_dict(orient="records"):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # optionally write CSV
    if output_csv:
        df.to_csv(output_csv, index=False)
    print(f"Parsed {len(df)} entries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the rule‑based Hiberno‑English parser.")
    parser.add_argument("--config", type=str, default=str(Path(__file__).resolve().parents[2] / "configs" / "rule_parser_config.yaml"), help="Path to YAML configuration file.")
    args = parser.parse_args()
    run_rule_parser(args.config)


if __name__ == "__main__":
    main()