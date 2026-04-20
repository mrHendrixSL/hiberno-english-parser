"""
scripts/run_genai_parser.py
===========================
Run the GenAI (LLM) extraction pipeline over rule-based output.

Usage
-----
  python scripts/run_genai_parser.py
  python scripts/run_genai_parser.py --config configs/genai_config.yaml
  python scripts/run_genai_parser.py --estimate-only

Requires ANTHROPIC_API_KEY in environment or .env file.
The script will resume from a partial checkpoint if the output file
already exists.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from src.shared.config_loader import load_config, resolve_path
from src.shared.io_utils import load_json
from src.genai.extractor import (
    load_prompt_config,
    estimate_cost,
    run_batch,
    build_eligible_sample,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # python-dotenv is optional


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GenAI extraction pipeline.")
    parser.add_argument("--config", default="configs/genai_config.yaml",
                        help="Path to genai_config.yaml")
    parser.add_argument("--estimate-only", action="store_true",
                        help="Print cost estimate and exit without calling the API")
    parser.add_argument("--input",  help="Override input path from config")
    parser.add_argument("--output", help="Override output path from config")
    args = parser.parse_args()

    _load_dotenv()

    cfg = load_config(args.config)

    input_path    = resolve_path(args.input  or cfg["paths"]["input"])
    output_path   = resolve_path(args.output or cfg["paths"]["output"])
    log_path      = resolve_path(cfg["paths"]["log"])
    batch_size    = cfg["extraction"]["batch_size"]
    delay         = cfg["extraction"]["rate_limit_delay"]
    checkpoint    = cfg["extraction"]["checkpoint_every"]

    rb_records = load_json(input_path, default=[])
    if not rb_records:
        logger.error("No rule-based records loaded from %s", input_path)
        sys.exit(1)

    eligible = build_eligible_sample(rb_records)
    logger.info("Eligible entries for extraction: %d / %d total", len(eligible), len(rb_records))

    estimate = estimate_cost(len(eligible), batch_size)

    if args.estimate_only:
        logger.info("Estimate only — exiting without calling the API.")
        return

    prompt_cfg = load_prompt_config(cfg)
    client     = anthropic.Anthropic()

    run_batch(
        sample=eligible,
        prompt_config=prompt_cfg,
        client=client,
        output_path=output_path,
        batch_size=batch_size,
        rate_limit_delay=delay,
        checkpoint_every=checkpoint,
        log_path=log_path,
    )


if __name__ == "__main__":
    main()
