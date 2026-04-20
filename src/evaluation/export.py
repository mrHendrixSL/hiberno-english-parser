"""
export.py
=========
Export comparison results to a multi-sheet Excel workbook.

Sheets produced:
  entries           — one row per entry, all fields flattened
  exact_agreement   — per-field exact agreement % (aggregate)
  token_similarity  — per-field ordered/unordered similarity (aggregate)
  field_presence    — per-field presence counts (aggregate)
  coverage          — coverage summary statistics
  misclassification — misclassification counts + per-entry flags
  stratum_agreement — exact agreement % by stratum × field
  disagreements     — classification disagreements
"""

from __future__ import annotations

import pandas as pd

from src.shared.schema import CONTENT_FIELDS, STRATUM_COLS, MISCLASS_COLS
from src.shared.io_utils import ensure_dir


def _serialise_cell(value) -> str:
    """Flatten any field value to a string suitable for an Excel cell."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(", ".join(f"{k}: {v}" for k, v in item.items() if v))
            else:
                parts.append(str(item))
        return " | ".join(parts)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v)
    return str(value)


def export_xlsx(data: dict, xlsx_path: str) -> None:
    """Write the comparison output dict to a multi-sheet Excel workbook."""
    ensure_dir(str(xlsx_path).rsplit("/", 1)[0] if "/" in str(xlsx_path) else ".")

    entries = data["entries"]
    agg     = data["aggregate"]
    strat   = agg.get("stratum_agreement", {})

    # ── Sheet 1: entries ──────────────────────────────────────────────────────
    entry_rows: list[dict] = []
    for e in entries:
        row: dict = {"para_id": e["para_id"], "full_text": e["full_text"]}
        for f in CONTENT_FIELDS:
            row[f"rb_{f}"]  = _serialise_cell(e["rb"].get(f))
            row[f"llm_{f}"] = _serialise_cell(e["llm"].get(f))
        cmp = e["comparison"]
        row["agree_pct"]          = cmp.get("agree_pct")
        row["rb_coverage_pct"]    = cmp.get("rb_coverage_pct")
        row["llm_coverage_pct"]   = cmp.get("llm_coverage_pct")
        row["any_misclassification"] = cmp.get("any_misclassification")
        for f in CONTENT_FIELDS:
            row[f"{f}_exact_match"]    = cmp["exact_agreement"].get(f)
            row[f"{f}_ordered_sim"]    = cmp["token_similarity"].get(f, {}).get("ordered")
            row[f"{f}_unordered_sim"]  = cmp["token_similarity"].get(f, {}).get("unordered")
        for flag in MISCLASS_COLS:
            if flag != "misclass_any":
                row[flag] = cmp["misclassification_flags"].get(flag)
        for s in STRATUM_COLS:
            row[s] = cmp["strata"].get(s)
        entry_rows.append(row)
    df_entries = pd.DataFrame(entry_rows)

    # ── Sheet 2: exact_agreement ──────────────────────────────────────────────
    df_exact = pd.DataFrame(
        [{"field": f, "exact_agreement_pct": v}
         for f, v in agg["exact_agreement_pct"].items()]
    ).sort_values("exact_agreement_pct", ascending=False).reset_index(drop=True)

    # ── Sheet 3: token_similarity ─────────────────────────────────────────────
    df_tok = pd.DataFrame(
        [{"field": f, "ordered_sim": v["ordered"], "unordered_sim": v["unordered"]}
         for f, v in agg["token_similarity"].items()]
    ).sort_values("ordered_sim", ascending=False).reset_index(drop=True)

    # ── Sheet 4: field_presence ───────────────────────────────────────────────
    df_pres = pd.DataFrame(
        [{"field": f, **v} for f, v in agg["field_presence"].items()]
    )

    # ── Sheet 5: coverage ─────────────────────────────────────────────────────
    df_cov = pd.DataFrame([agg["coverage"]])

    # ── Sheet 6: misclassification ────────────────────────────────────────────
    df_misclass = pd.DataFrame(
        [{"flag": k, "count": v}
         for k, v in agg["misclassification_counts"].items()]
    ).sort_values("count", ascending=False).reset_index(drop=True)

    # ── Sheet 7: stratum_agreement ────────────────────────────────────────────
    strat_rows: list[dict] = []
    for s, sv in strat.items():
        for f in CONTENT_FIELDS:
            strat_rows.append({
                "stratum":              s.replace("stratum_", ""),
                "n":                    sv["n"],
                "field":                f,
                "exact_agreement_pct":  sv["exact_agreement_pct"].get(f),
                "ordered_sim":          sv["mean_token_similarity"].get(f, {}).get("ordered"),
                "unordered_sim":        sv["mean_token_similarity"].get(f, {}).get("unordered"),
            })
    df_strat = pd.DataFrame(strat_rows)

    # ── Sheet 8: disagreements ────────────────────────────────────────────────
    df_disagree = pd.DataFrame(data.get("classification_disagreements", []))

    # ── Write workbook ────────────────────────────────────────────────────────
    from pathlib import Path
    ensure_dir(Path(xlsx_path).parent)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_entries.to_excel(writer,  sheet_name="entries",           index=False)
        df_exact.to_excel(writer,    sheet_name="exact_agreement",   index=False)
        df_tok.to_excel(writer,      sheet_name="token_similarity",  index=False)
        df_pres.to_excel(writer,     sheet_name="field_presence",    index=False)
        df_cov.to_excel(writer,      sheet_name="coverage",          index=False)
        df_misclass.to_excel(writer, sheet_name="misclassification", index=False)
        df_strat.to_excel(writer,    sheet_name="stratum_agreement", index=False)
        if not df_disagree.empty:
            df_disagree.to_excel(writer, sheet_name="disagreements", index=False)

    print(f"Excel workbook written → {xlsx_path}")
    print(f"  Sheets: entries ({len(df_entries)} rows), exact_agreement, "
          f"token_similarity, field_presence, coverage, "
          f"misclassification, stratum_agreement, disagreements")
