"""
scripts/run_genai_rerun.py
==========================
Re-extract flagged entries with an improved prompt and merge results
back into the main LLM output.

Usage
-----
  python scripts/run_genai_rerun.py
  python scripts/run_genai_rerun.py --config configs/genai_config.yaml

Requires ANTHROPIC_API_KEY in environment or .env file.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.config_loader import load_config, resolve_path
from src.genai.extractor import load_prompt_config
from src.genai.rerun import rerun_and_merge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-run flagged GenAI entries.")
    parser.add_argument("--config", default="configs/genai_config.yaml",
                        help="Path to genai_config.yaml")
    args = parser.parse_args()

    _load_dotenv()

    cfg = load_config(args.config)

    llm_output_path    = resolve_path(cfg["paths"]["output"])
    rb_path            = resolve_path(cfg["paths"]["input"])
    rerun_output_path  = resolve_path(cfg["rerun"]["output"])
    merged_output_path = resolve_path(cfg["rerun"]["merged"])
    rerun_prompt_file  = resolve_path(cfg["rerun"]["prompt"])
    coverage_threshold = cfg["rerun"].get("coverage_threshold", 70.0)

    # Build a prompt config using the rerun prompt
    rerun_cfg = dict(cfg)
    rerun_cfg["prompt_file"] = str(rerun_prompt_file)
    prompt_cfg = load_prompt_config(rerun_cfg)

    rerun_and_merge(
        llm_output_path=llm_output_path,
        rb_path=rb_path,
        prompt_config=prompt_cfg,
        rerun_output_path=rerun_output_path,
        merged_output_path=merged_output_path,
        coverage_threshold=coverage_threshold,
    )


if __name__ == "__main__":
    main()
