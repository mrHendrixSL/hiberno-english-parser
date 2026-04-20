"""
scripts/run_rule_parser.py
==========================
Run the rule-based parser over a paragraphs JSON file.

Usage
-----
  python scripts/run_rule_parser.py
  python scripts/run_rule_parser.py --config configs/rule_parser_config.yaml
  python scripts/run_rule_parser.py --input data/paragraphs.json --output data/rule_based_output.json

The script filters out section headers before parsing and reports
coverage statistics on completion.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.config_loader import load_config, resolve_path, REPO_ROOT
from src.shared.io_utils import load_json, save_json
from src.rule_based.parser import parse_all, coverage_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hiberno-English rule-based parser.")
    parser.add_argument("--config", default="configs/rule_parser_config.yaml",
                        help="Path to rule_parser_config.yaml")
    parser.add_argument("--input",  help="Override input path from config")
    parser.add_argument("--output", help="Override output path from config")
    args = parser.parse_args()

    cfg = load_config(args.config)

    input_path  = resolve_path(args.input  or cfg["paths"]["input"])
    output_path = resolve_path(args.output or cfg["paths"]["output"])
    warn_below  = cfg.get("coverage", {}).get("warn_below", 80)

    logger.info("Input:  %s", input_path)
    logger.info("Output: %s", output_path)

    paragraphs = load_json(input_path)
    if not paragraphs:
        logger.error("No paragraphs loaded from %s", input_path)
        sys.exit(1)

    logger.info("Parsing %d paragraphs...", len(paragraphs))
    records = parse_all(paragraphs)

    save_json(output_path, records)
    logger.info("Written %d records → %s", len(records), output_path)

    report = coverage_report(records)
    logger.info("Mean coverage: %.1f%%", report["mean_coverage"] or 0)
    if report["below_50"]:
        logger.warning(
            "%d entries below 50%% coverage (check coverage_uncovered for details)",
            len(report["below_50"]),
        )
    elif report["below_80"] and warn_below <= 80:
        logger.info(
            "%d entries below %d%% coverage",
            len(report["below_80"]), warn_below,
        )


if __name__ == "__main__":
    main()
