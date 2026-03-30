#!/usr/bin/env python
"""Run the GenAI parser on a collection of dictionary entries.

This script iterates over a JSON/JSONL input file containing entry IDs
and texts, queries an LLM to extract structured fields and appends the
results to an output JSONL file. Errors are logged separately. The
script respects configuration settings such as the maximum number of
entries to process and how many previously unfinished entries to skip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
import os

# Extend sys.path to include the local ``src`` directory. This allows
# importing internal packages (shared, genai, etc.) without requiring
# installation as a site‑package.
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_PATH = BASE_DIR / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from shared.config import load_config  # type: ignore
from genai.parser import GenAIParser, load_prompt  # type: ignore


def read_input(path: str | Path) -> List[Dict[str, Any]]:
    """Read a JSON or JSONL file of entries to parse.

    Each entry must contain ``entry_id`` and ``entry_text`` fields. The
    function detects whether the input is JSON (a list of objects) or
    JSON Lines (one object per line) based on file extension.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    entries: List[Dict[str, Any]] = []
    if p.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                # allow a dict mapping IDs to texts
                entries = [{"entry_id": k, "entry_text": v} for k, v in data.items()]
            else:
                raise ValueError("JSON input must be a list or object mapping IDs to texts")
        else:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    entries.append(obj)
    else:
        raise ValueError(f"Unsupported input file format: {p.suffix}")
    return entries


def run_genai_parser(config_path: str | Path) -> None:
    cfg = load_config(config_path)
    cfg_dir = Path(config_path).resolve().parent
    input_json = Path(cfg_dir, cfg.input_json).resolve()
    output_jsonl = Path(cfg_dir, cfg.output_jsonl).resolve()
    error_jsonl = Path(cfg_dir, cfg.error_jsonl).resolve()
    # ensure output dirs exist
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    error_jsonl.parent.mkdir(parents=True, exist_ok=True)
    # load prompts
    proj_root = Path(__file__).resolve().parents[1]
    system_prompt = load_prompt(proj_root / "prompts" / "system_prompt.txt")
    parser_prompt = load_prompt(proj_root / "prompts" / "parser_prompt.txt")
    # instantiate parser
    parser = GenAIParser(
        base_url=cfg.get("base_url"),
        model_name=cfg.model_name,
        system_prompt=system_prompt,
        parser_prompt=parser_prompt,
        temperature=float(cfg.temperature),
        max_tokens=int(cfg.max_tokens),
    )
    # read input
    entries = read_input(input_json)
    # load existing done IDs
    done_ids = set()
    if output_jsonl.exists():
        with output_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    done_ids.add(str(obj.get("entry_id")))
                except Exception:
                    pass
    # process entries
    max_new_rows = cfg.get("max_new_rows")
    skip_unfinished_rows = int(cfg.get("skip_unfinished_rows", 0))
    processed_new = 0
    seen_unfinished = 0
    with output_jsonl.open("a", encoding="utf-8") as out_f, error_jsonl.open("a", encoding="utf-8") as err_f:
        for entry in entries:
            entry_id = str(entry.get("entry_id"))
            entry_text = entry.get("entry_text", "")
            if entry_id in done_ids:
                continue
            seen_unfinished += 1
            if seen_unfinished <= skip_unfinished_rows:
                continue
            if max_new_rows is not None and processed_new >= max_new_rows:
                break
            print(f"Processing {entry_id} | batch item {processed_new + 1}")
            parsed, flags, needs_review, error = parser.parse_entry(entry_id, entry_text)
            if parsed is None:
                err_f.write(json.dumps({"entry_id": entry_id, "error": error, "raw": entry_text}, ensure_ascii=False) + "\n")
                err_f.flush()
                continue
            record = {
                "entry_id": entry_id,
                "source_text": entry_text,
                "data": parsed,
                "flags": flags,
                "needs_review": needs_review,
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            processed_new += 1
    print(f"Processed {processed_new} new entries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GenAI Hiberno‑English parser.")
    parser.add_argument("--config", type=str, default=str(Path(__file__).resolve().parents[2] / "configs" / "genai_config.yaml"), help="Path to YAML configuration file.")
    args = parser.parse_args()
    run_genai_parser(args.config)


if __name__ == "__main__":
    main()