"""
rerun.py
========
Re-extracts flagged entries using an improved prompt, then merges the
improved records back into the main LLM output.

Entries are flagged when they show signs of extraction problems:
  - who_adds examples dropped or absorbed into definition
  - coverage below threshold
  - medium parse_confidence
  - examples dropped relative to rule-based output
  - chained etymology collapsed to single source
  - numbered senses not split into a list
  - cross-reference missed
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

import anthropic

from src.shared.io_utils import load_json, save_json
from src.genai.extractor import load_prompt_config, run_batch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flag detection
# ---------------------------------------------------------------------------

def flag_entries(llm_records: list, rb_index: dict) -> dict[int, list[str]]:
    """Return ``{para_id: [reasons]}`` for entries worth re-running."""
    flagged: dict[int, list[str]] = {}

    for r in llm_records:
        pid     = r["para_id"]
        rb      = rb_index.get(pid, {})
        ft      = r.get("full_text", "") or ""
        reasons: list[str] = []

        if "who adds" in ft.lower():
            if rb.get("examples") and not r.get("examples"):
                reasons.append("who_adds:examples_dropped")
            elif r.get("examples") and "'" in str(r.get("definition") or ""):
                reasons.append("who_adds:example_in_definition")

        cov = r.get("coverage_pct")
        if cov is not None and cov < 70:
            reasons.append(f"low_coverage:{cov}")

        if r.get("parse_confidence") == "medium":
            reasons.append("medium_confidence")

        if rb.get("examples") and not r.get("examples"):
            if not any(reason.startswith("who_adds") for reason in reasons):
                reasons.append("examples_dropped")

        rb_etym  = str(rb.get("etymology") or "")
        llm_etym = str(r.get("etymology") or "")
        if rb_etym.count("<") > 1 and llm_etym.count("<") == 1:
            reasons.append("chained_etym_collapsed")

        if isinstance(rb.get("definition"), list) and isinstance(r.get("definition"), str):
            reasons.append("numbered_senses_not_split")

        if rb.get("cross_references") and not r.get("cross_references"):
            reasons.append("cross_ref_missed")

        if reasons:
            flagged[pid] = reasons

    return flagged


def _summarise_flags(flagged: dict) -> None:
    """Log a breakdown of flag types."""
    counts: dict[str, int] = defaultdict(int)
    for reasons in flagged.values():
        for r in reasons:
            counts[r.split(":")[0]] += 1
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        logger.info("  %-30s %d", k, v)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def rerun_and_merge(
    llm_output_path: str | Path,
    rb_path: str | Path,
    prompt_config: dict,
    rerun_output_path: str | Path,
    merged_output_path: str | Path,
    coverage_threshold: float = 70.0,
) -> list:
    """Flag problematic entries, re-extract them, and merge back into the corpus.

    Parameters
    ----------
    llm_output_path:
        Path to the existing LLM extraction output JSON.
    rb_path:
        Path to the rule-based output JSON (used as input for re-extraction).
    prompt_config:
        Loaded prompt config dict (pass the improved/v2 prompt).
    rerun_output_path:
        Where to write the re-extracted records.
    merged_output_path:
        Where to write the merged output (updated originals + re-runs).
    coverage_threshold:
        Flag entries with coverage below this percentage.
    """
    llm_records: list = load_json(llm_output_path, default=[])
    rb_records: list  = load_json(rb_path, default=[])

    rb_index  = {r["para_id"]: r for r in rb_records}
    llm_index = {r["para_id"]: r for r in llm_records}

    flagged = flag_entries(llm_records, rb_index)
    logger.info("Flagged entries: %d", len(flagged))
    _summarise_flags(flagged)

    rerun_sample = [
        rb_index[pid]
        for pid in sorted(flagged)
        if pid in rb_index
    ]
    logger.info("Re-run sample size: %d", len(rerun_sample))

    client = anthropic.Anthropic()
    rerun_records = run_batch(
        sample=rerun_sample,
        prompt_config=prompt_config,
        client=client,
        output_path=rerun_output_path,
        log_path=Path(rerun_output_path).parent / "rerun.log",
        rate_limit_delay=2.0,
        checkpoint_every=50,
    )

    rerun_index = {r["para_id"]: r for r in rerun_records}

    merged: list = []
    replaced     = 0
    for r in llm_records:
        pid = r["para_id"]
        if pid in rerun_index:
            new_rec               = rerun_index[pid].copy()
            new_rec["rerun_v2"]   = True
            new_rec["v1_reasons"] = flagged.get(pid, [])
            merged.append(new_rec)
            replaced += 1
        else:
            merged.append(r)

    logger.info("Merged: %d records replaced", replaced)
    save_json(merged_output_path, merged)
    logger.info("Saved merged output → %s", merged_output_path)

    print(f"\nDone.")
    print(f"  Original:  {llm_output_path}  ({len(llm_records)} records)")
    print(f"  Re-run:    {rerun_output_path}  ({len(rerun_records)} records)")
    print(f"  Merged:    {merged_output_path}  ({len(merged)} records, {replaced} updated)")

    return merged
