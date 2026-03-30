#!/usr/bin/env python
"""Evaluate and compare rule‑based and GenAI parser outputs.

This script loads the outputs produced by ``run_rule_parser.py`` and
``run_genai_parser.py``, normalises them into a shared schema, applies
optional mapping files for POS and region labels, merges the datasets
and generates summary reports. The merged output and reports are
written to the directory specified in the configuration file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

# Extend sys.path to include the local ``src`` directory. This allows
# importing internal packages (shared, evaluation) without requiring
# installation as a site‑package. The scripts directory is one level
# below the project root, so ``SRC_PATH`` points to ``root/src``.
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_PATH = BASE_DIR / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from shared.config import load_config  # type: ignore
from evaluation.normalize import read_jsonl, normalize_rule, normalize_genai  # type: ignore
from evaluation.merge import merge_outputs  # type: ignore
from evaluation.reports import write_presence_summary, write_exact_match_summary  # type: ignore


def flatten_genai(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "data" in out.columns:
        data_flat = pd.json_normalize(out["data"]).add_prefix("data.")
        out = pd.concat([out.drop(columns=["data"]), data_flat], axis=1)
    if "flags" in out.columns:
        flags_flat = pd.json_normalize(out["flags"]).add_prefix("flags.")
        out = pd.concat([out.drop(columns=["flags"]), flags_flat], axis=1)
    return out


def apply_mapping(values: List[str], mapping: Dict[str, str]) -> List[str]:
    if not mapping:
        return values
    return list(dict.fromkeys([mapping.get(v, v) for v in values if v is not None]))


def run_evaluation(config_path: str | Path) -> None:
    cfg = load_config(config_path)
    cfg_dir = Path(config_path).resolve().parent
    rule_path = Path(cfg_dir, cfg.rule_output).resolve()
    genai_path = Path(cfg_dir, cfg.genai_output).resolve()
    pos_map_path = None if not cfg.get("pos_map") else Path(cfg_dir, cfg.pos_map).resolve()
    region_map_path = None if not cfg.get("region_map") else Path(cfg_dir, cfg.region_map).resolve()
    output_dir = Path(cfg_dir, cfg.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # load raw outputs
    rule_raw = read_jsonl(rule_path)
    genai_raw = read_jsonl(genai_path)
    # flatten genai nested structure
    genai_flat = flatten_genai(genai_raw)
    # normalise
    # rule pronunciations columns defined in the original output
    rule_pron_cols = [
        "pronunciation",
        "pronunciation_2",
        "pronunciation_3",
        "pronunciation_4",
    ]
    rule_norm = normalize_rule(rule_raw, rule_pron_cols, "part_of_speech")
    genai_norm = normalize_genai(genai_flat)
    # load mappings
    pos_map: Dict[str, str] = {}
    region_map: Dict[str, str] = {}
    if pos_map_path and pos_map_path.exists():
        pos_map = json.loads(pos_map_path.read_text(encoding="utf-8"))
    if region_map_path and region_map_path.exists():
        region_map = json.loads(region_map_path.read_text(encoding="utf-8"))
    # apply mappings
    if pos_map:
        rule_norm["part_of_speech"] = rule_norm["part_of_speech"].apply(lambda x: apply_mapping(x, pos_map))
        genai_norm["part_of_speech"] = genai_norm["part_of_speech"].apply(lambda x: apply_mapping(x, pos_map))
    if region_map:
        rule_norm["region_mentions"] = rule_norm["region_mentions"].apply(lambda x: apply_mapping(x, region_map))
        genai_norm["region_mentions"] = genai_norm["region_mentions"].apply(lambda x: apply_mapping(x, region_map))
    # merge outputs
    merged = merge_outputs(rule_norm, genai_norm)
    # write merged output JSONL
    merged_jsonl_path = output_dir / "merged_output.jsonl"
    with merged_jsonl_path.open("w", encoding="utf-8") as f:
        for record in merged.to_dict(orient="records"):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # write presence and exact match summaries
    write_presence_summary(merged, output_dir / "presence_summary.csv")
    write_exact_match_summary(merged, output_dir / "exact_match_summary.csv")
    # optionally write Excel summary
    try:
        with pd.ExcelWriter(output_dir / "summaries.xlsx") as writer:
            merged.to_excel(writer, sheet_name="merged", index=False)
            rule_norm.to_excel(writer, sheet_name="rule_norm", index=False)
            genai_norm.to_excel(writer, sheet_name="genai_norm", index=False)
    except Exception:
        # Excel support may not be available; ignore if writing fails
        pass
    print(f"Evaluation complete. Merged dataset size: {len(merged)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate and compare parser outputs.")
    parser.add_argument("--config", type=str, default=str(Path(__file__).resolve().parents[2] / "configs" / "evaluation_config.yaml"), help="Path to YAML configuration file.")
    args = parser.parse_args()
    run_evaluation(args.config)


if __name__ == "__main__":
    main()