"""
preprocessing.py
================
Merge rule-based and LLM parser outputs into a single comparison DataFrame.

Design notes:
  - Missing LLM values are stored as None (not mirrored from RB), so that
    downstream metrics correctly reflect absent LLM extractions.
  - Entry alignment is on para_id.
  - Homonym-index normalisation is applied to LLM headwords.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from src.shared.io_utils import load_json
from src.shared.schema import KEEP_FIELDS

logger = logging.getLogger(__name__)

COLUMN_ORDER = ["para_id", "full_text"] + [
    col
    for field in KEEP_FIELDS
    for col in (f"{field}_Rule", f"{field}_LLM")
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_homonym_index(records: list) -> list:
    """Normalise LLM headwords: strip trailing digit into homonym_index."""
    for record in records:
        hw = record.get("headword", "") or ""
        m  = re.match(r"^(.*?)(\d+)$", hw)
        if m:
            record["homonym_index"] = int(m.group(2))
            record["headword"]      = m.group(1).strip()
    return records


# ---------------------------------------------------------------------------
# Main merge function
# ---------------------------------------------------------------------------

def build_merged(
    rb_path: str,
    llm_path: str,
) -> pd.DataFrame:
    """Merge rule-based and LLM outputs into a single DataFrame.

    Parameters
    ----------
    rb_path:
        Path to rule-based parsed_entries JSON.
    llm_path:
        Path to LLM extraction output JSON.

    Returns
    -------
    DataFrame with columns para_id, full_text, and for each field in
    KEEP_FIELDS: ``{field}_Rule`` and ``{field}_LLM``.
    Missing LLM values are represented as None (not mirrored from RB).
    """
    rb_records  = load_json(rb_path, default=[])
    llm_records = load_json(llm_path, default=[])

    llm_records = _extract_homonym_index(llm_records)

    llm_lookup: dict = {
        rec["para_id"]: {f: rec.get(f) for f in KEEP_FIELDS}
        for rec in llm_records
    }

    rows: list       = []
    n_matched        = 0
    n_not_matched    = 0
    disagreements: list = []

    for rb in rb_records:
        pid       = rb["para_id"]
        llm_entry = llm_lookup.get(pid)

        if llm_entry is not None:
            n_matched += 1
        else:
            n_not_matched += 1

        row = {"para_id": pid, "full_text": rb.get("full_text")}
        for field in KEEP_FIELDS:
            row[f"{field}_Rule"] = rb.get(field)
            # Use None for missing LLM values — do NOT mirror RB values
            row[f"{field}_LLM"]  = llm_entry.get(field) if llm_entry is not None else None
        rows.append(row)

        rb_type  = rb.get("entry_type")
        llm_type = llm_entry.get("entry_type") if llm_entry else None
        if rb_type == "full" and llm_type is not None and llm_type != "full":
            disagreements.append({
                "para_id": pid,
                "headword": rb.get("headword", ""),
                "llm_type": llm_type,
            })

    df = pd.DataFrame(rows, columns=COLUMN_ORDER)

    logger.info(
        "Merged DataFrame: %d rows  (LLM matched=%d, unmatched=%d, "
        "classification disagreements=%d)",
        len(df), n_matched, n_not_matched, len(disagreements),
    )
    for d in disagreements:
        logger.debug(
            "  Classification disagreement: para_id=%s  headword=%s  llm_type=%s",
            d["para_id"], d["headword"], d["llm_type"],
        )

    return df
