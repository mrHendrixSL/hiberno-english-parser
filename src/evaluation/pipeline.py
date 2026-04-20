"""
pipeline.py
===========
Orchestrates the full DataFrame-based evaluation pipeline:

  1. Merge rule-based + LLM outputs (preprocessing)
  2. Add coverage metrics (coverage)
  3. Add evaluation metrics (metrics)
  4. Compute aggregate statistics (aggregation)
  5. Build per-entry comparison records
  6. Write comparison.json
  7. Optionally export to Excel (export)
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

from src.evaluation.preprocessing import build_merged
from src.evaluation.coverage      import add_coverage
from src.evaluation.metrics       import add_all_metrics
from src.evaluation.aggregation   import (
    compute_aggregate,
    compute_stratum_agreement,
    build_entry_records,
    _to_python,
)
from src.evaluation.export        import export_xlsx
from src.shared.io_utils          import load_json, ensure_dir

logger = logging.getLogger(__name__)


def run_pipeline(
    rb_path: str,
    llm_path: str,
    output_json: str,
    output_xlsx: str | None = None,
    excel_export: bool = True,
) -> dict:
    """Run the full evaluation pipeline.

    Parameters
    ----------
    rb_path:      Path to rule-based output JSON.
    llm_path:     Path to LLM extraction output JSON.
    output_json:  Where to write comparison.json.
    output_xlsx:  Where to write comparison.xlsx (derived from output_json if None).
    excel_export: Whether to produce an Excel workbook.
    """
    print("=" * 60)
    print("Step 1: Building merged DataFrame...")
    df = build_merged(rb_path, llm_path)

    print("\nStep 2: Adding coverage metrics...")
    df = add_coverage(df)

    print("\nStep 3: Adding evaluation metrics...")
    df = add_all_metrics(df)

    print("\nStep 4: Computing aggregate statistics...")
    agg   = compute_aggregate(df)
    strat = compute_stratum_agreement(df)

    print("Step 5: Building entry records...")
    entries = build_entry_records(df)

    # Classification disagreements
    rb_all       = load_json(rb_path, default=[])
    llm_all      = load_json(llm_path, default=[])
    llm_lookup   = {r["para_id"]: r for r in llm_all}
    disagreements = [
        {
            "para_id":  rb["para_id"],
            "headword": str(rb.get("headword", "")),
            "full_text":str(rb.get("full_text", "")),
            "rb_type":  "full",
            "llm_type": str(llm_lookup[rb["para_id"]].get("entry_type")),
        }
        for rb in rb_all
        if rb.get("entry_type") == "full"
        and rb["para_id"] in llm_lookup
        and llm_lookup[rb["para_id"]].get("entry_type") != "full"
    ]

    n_cross_ref = sum(1 for r in rb_all if r.get("entry_type") == "cross_ref")
    n_header    = sum(1 for r in rb_all if r.get("entry_type") == "header")
    n_rb_full   = sum(1 for r in rb_all if r.get("entry_type") == "full")
    n_llm_matched = sum(1 for r in rb_all if r["para_id"] in llm_lookup)

    output = {
        "meta": {
            "n_total":                    len(entries),
            "n_rb_full":                  n_rb_full,
            "n_rb_cross_ref":             n_cross_ref,
            "n_rb_header":                n_header,
            "n_llm_matched":              n_llm_matched,
            "n_llm_unmatched":            len(rb_all) - n_llm_matched,
            "n_classification_disagreements": len(disagreements),
            "rb_file":                    rb_path,
            "llm_file":                   llm_path,
            "generated":                  datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "classification_disagreements": disagreements,
        "aggregate": {
            **agg,
            "stratum_agreement": strat,
        },
        "entries": entries,
    }

    out_path = Path(output_json)
    ensure_dir(out_path.parent)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=_to_python)

    print(f"\n{'=' * 60}")
    print(f"comparison.json written → {output_json}")
    print(f"  Total entries: {len(entries)}")
    print(f"  RB full / cross_ref / header: {n_rb_full} / {n_cross_ref} / {n_header}")
    print(f"  LLM matched: {n_llm_matched}")
    print(f"  Classification disagreements: {len(disagreements)}")
    print(f"\n  Coverage (all rows):")
    print(f"    RB  token: {agg['coverage']['mean_rb_coverage_pct']}%  "
          f"char: {agg['coverage']['mean_rb_char_pct']}%")
    print(f"    LLM token: {agg['coverage']['mean_llm_coverage_pct']}%  "
          f"char: {agg['coverage']['mean_llm_char_pct']}%")

    if excel_export:
        xlsx = output_xlsx or str(out_path).replace(".json", ".xlsx")
        print("\nStep 6: Exporting to Excel...")
        export_xlsx(output, xlsx)

    return output
