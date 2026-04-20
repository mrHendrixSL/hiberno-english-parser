"""
scripts/run_evaluation.py
=========================
Run the full evaluation pipeline comparing rule-based and LLM outputs.

Usage
-----
  python scripts/run_evaluation.py
  python scripts/run_evaluation.py --config configs/evaluation_config.yaml
  python scripts/run_evaluation.py --rb data/rule_based_output.json --llm outputs/genai/llm_output_v2.json

Produces:
  - outputs/evaluation/comparison.json  — full per-entry comparison data
  - outputs/evaluation/comparison.xlsx  — 8-sheet Excel workbook (if enabled)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.config_loader import load_config, resolve_path
from src.evaluation.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hiberno-English evaluation pipeline.")
    parser.add_argument("--config", default="configs/evaluation_config.yaml",
                        help="Path to evaluation_config.yaml")
    parser.add_argument("--rb",     help="Override rule-based input path from config")
    parser.add_argument("--llm",    help="Override LLM input path from config")
    parser.add_argument("--output", help="Override output JSON path from config")
    parser.add_argument("--no-excel", action="store_true",
                        help="Skip Excel export")
    args = parser.parse_args()

    cfg = load_config(args.config)

    rb_path     = str(resolve_path(args.rb     or cfg["paths"]["rule_based"]))
    llm_path    = str(resolve_path(args.llm    or cfg["paths"]["llm"]))
    output_json = str(resolve_path(args.output or cfg["paths"]["output_json"]))
    output_xlsx = str(resolve_path(cfg["paths"]["output_xlsx"]))

    excel_export = (not args.no_excel) and cfg["settings"].get("excel_export", True)

    run_pipeline(
        rb_path=rb_path,
        llm_path=llm_path,
        output_json=output_json,
        output_xlsx=output_xlsx if excel_export else None,
        excel_export=excel_export,
    )


if __name__ == "__main__":
    main()
