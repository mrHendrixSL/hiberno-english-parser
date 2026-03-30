"""Reporting helpers for evaluation outputs.

These helpers wrap the computation of presence and exact match summaries
and provide convenient functions to write them to disk in various
formats (JSONL, CSV or Excel). The functions accept DataFrames as
returned by :mod:`hiberno_english_parser.src.evaluation.merge`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .merge import compute_presence_summary, compute_exact_match_summary


def write_presence_summary(merged_df: pd.DataFrame, dest: str | Path) -> None:
    summary = compute_presence_summary(merged_df)
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(p, index=False)


def write_exact_match_summary(merged_df: pd.DataFrame, dest: str | Path) -> None:
    summary = compute_exact_match_summary(merged_df)
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(p, index=False)
