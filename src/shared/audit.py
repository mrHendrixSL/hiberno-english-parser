"""
audit.py
========
Version-management and diff utilities for parsed-entry JSON outputs.

Workflow:
  1. snapshot_live_output()  — archive current JSON before overwriting
  2. compare_with_previous_version()  — diff archived vs. new entries
  3. write_diff_outputs()  — persist JSON + XLSX diff reports
  4. prepare_versioned_output()  — orchestrate all three steps
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .io_utils import load_json, save_json, ensure_dir

AUTO_IGNORE_FIELDS: frozenset[str] = frozenset({"changed", "changed_fields"})


# ---------------------------------------------------------------------------
# Normalisation for comparison
# ---------------------------------------------------------------------------

def _normalise_for_compare(value: Any) -> Any:
    """Normalise a field value to eliminate harmless formatting differences."""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, list):
        return [_normalise_for_compare(v) for v in value]
    if isinstance(value, dict):
        return {
            str(k): _normalise_for_compare(v)
            for k, v in sorted(value.items(), key=lambda x: str(x[0]))
        }
    return value


# ---------------------------------------------------------------------------
# Entry key
# ---------------------------------------------------------------------------

def _entry_key(entry: dict[str, Any]) -> str:
    """Return a stable primary key for an entry dict.

    Prefers ``para_id``; falls back to ``paragraph_id``.
    """
    for field in ("para_id", "paragraph_id"):
        val = entry.get(field)
        if val is not None:
            return str(val)
    raise KeyError(f"Entry missing both 'para_id' and 'paragraph_id': {list(entry)[:5]}")


# ---------------------------------------------------------------------------
# Field diff
# ---------------------------------------------------------------------------

def _diff_entry(
    old: dict[str, Any] | None,
    new: dict[str, Any],
    ignore: set[str] | None = None,
) -> tuple[bool, list[str], dict[str, dict[str, Any]]]:
    """Compare two entry dicts field by field.

    Returns ``(changed, changed_fields, field_diffs)``.
    """
    ignore = (ignore or set()) | AUTO_IGNORE_FIELDS

    if old is None:
        fields = sorted(k for k in new if k not in ignore)
        diffs = {k: {"old": None, "new": new.get(k)} for k in fields}
        return True, fields, diffs

    all_fields = sorted(set(old) | set(new))
    changed_fields: list[str] = []
    field_diffs: dict[str, dict[str, Any]] = {}

    for field in all_fields:
        if field in ignore:
            continue
        ov = _normalise_for_compare(old.get(field))
        nv = _normalise_for_compare(new.get(field))
        if ov != nv:
            changed_fields.append(field)
            field_diffs[field] = {"old": old.get(field), "new": new.get(field)}

    return bool(changed_fields), changed_fields, field_diffs


# ---------------------------------------------------------------------------
# Versioning helpers
# ---------------------------------------------------------------------------

def _manifest_path(base_dir: Path) -> Path:
    return base_dir / "manifests" / "version_manifest.json"


def _load_manifest(base_dir: Path) -> dict[str, Any]:
    manifest = load_json(_manifest_path(base_dir))
    return manifest if manifest else {"latest_version": 0, "versions": []}


def _save_manifest(base_dir: Path, manifest: dict[str, Any]) -> None:
    save_json(_manifest_path(base_dir), manifest)


def _next_version(base_dir: Path) -> int:
    return int(_load_manifest(base_dir).get("latest_version", 0)) + 1


def _fmt_version(n: int) -> str:
    return f"v{n:03d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def snapshot_live_output(
    live_path: Path,
    base_dir: Path,
    label: str = "parsed_entries",
) -> Path | None:
    """Copy the current live JSON into the versioned archive.

    Returns the archived path, or None if *live_path* does not exist.
    """
    if not live_path.exists():
        return None

    version_num = _next_version(base_dir)
    version_str = _fmt_version(version_num)
    archived = base_dir / "versions" / f"{label}_{version_str}.json"
    ensure_dir(archived.parent)
    shutil.copy2(live_path, archived)

    manifest = _load_manifest(base_dir)
    manifest["latest_version"] = version_num
    manifest["versions"].append({
        "version": version_str,
        "path": str(archived),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "archived_live_output",
    })
    _save_manifest(base_dir, manifest)
    return archived


def compare_with_previous_version(
    previous: list[dict[str, Any]] | None,
    current: list[dict[str, Any]],
    ignore: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Diff *previous* against *current*, tagging each entry with change info.

    Returns ``(enriched_entries, diff_rows)``.
    """
    prev_map = {_entry_key(e): e for e in (previous or [])}
    ignore_set = set(ignore or [])
    enriched: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []

    for entry in current:
        key = _entry_key(entry)
        changed, changed_fields, field_diffs = _diff_entry(
            prev_map.get(key), entry, ignore_set
        )
        e = {**entry, "changed": changed, "changed_fields": changed_fields}
        enriched.append(e)
        if changed:
            diff_rows.append({
                "entry_key": key,
                "para_id": entry.get("para_id"),
                "headword_raw": entry.get("headword_raw"),
                "changed": True,
                "changed_fields": changed_fields,
                "field_diffs": field_diffs,
            })

    return enriched, diff_rows


def write_diff_outputs(
    diff_rows: list[dict[str, Any]],
    base_dir: Path,
    from_version: str,
    to_label: str = "current",
    label: str = "parsed_entries",
) -> tuple[Path, Path]:
    """Write JSON and XLSX diff reports.

    Returns ``(json_path, xlsx_path)``.
    """
    stem = f"{label}_diff_{from_version}_to_{to_label}"
    json_path = base_dir / "diffs" / f"{stem}.json"
    xlsx_path = base_dir / "diffs" / f"{stem}.xlsx"

    save_json(json_path, diff_rows)

    flat: list[dict] = []
    for row in diff_rows:
        for field, vals in row.get("field_diffs", {}).items():
            flat.append({
                "entry_key": row.get("entry_key"),
                "para_id": row.get("para_id"),
                "headword_raw": row.get("headword_raw"),
                "field": field,
                "old_value": json.dumps(vals.get("old"), ensure_ascii=False),
                "new_value": json.dumps(vals.get("new"), ensure_ascii=False),
            })

    ensure_dir(xlsx_path.parent)
    pd.DataFrame(flat).to_excel(str(xlsx_path), index=False)
    return json_path, xlsx_path


def prepare_versioned_output(
    current: list[dict[str, Any]],
    live_path: Path,
    base_dir: Path,
    label: str = "parsed_entries",
    ignore: list[str] | None = None,
) -> dict[str, Any]:
    """Archive → diff → return enriched entries and diff metadata.

    Call this *before* overwriting the live output file.
    """
    ensure_dir(base_dir)
    archived = snapshot_live_output(live_path, base_dir, label)

    previous: list[dict] | None = None
    prev_version: str | None = None
    if archived and archived.exists():
        previous = load_json(archived, default=[])
        m = re.search(r"(v\d{3})", archived.name)
        prev_version = m.group(1) if m else "previous"

    enriched, diff_rows = compare_with_previous_version(previous, current, ignore)

    diff_json_path = diff_xlsx_path = None
    if prev_version is not None:
        diff_json_path, diff_xlsx_path = write_diff_outputs(
            diff_rows, base_dir, prev_version, "current", label
        )

    return {
        "entries": enriched,
        "archived_previous_path": archived,
        "previous_version": prev_version,
        "diff_rows": diff_rows,
        "diff_json_path": diff_json_path,
        "diff_xlsx_path": diff_xlsx_path,
    }
