"""
extractor.py
============
Calls a Claude-compatible API in batches to extract structured fields from
raw dictionary entries.

Features:
  - Batch processing (configurable batch_size)
  - Resume from checkpoint
  - Exponential backoff on rate-limit / API errors
  - Persistent file logging
  - tqdm progress bar
  - Cost estimation
  - Prompt loaded from a plain text file (not embedded in code)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import anthropic
from tqdm import tqdm

from src.shared.schema import EXTRACTED_FIELDS, PIPELINE_INJECTED
from src.shared.normalisation import normalise_fullwidth
from src.shared.io_utils import save_json, ensure_dir
from src.rule_based.parser import check_coverage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost estimation constants  (approximate; adjust if model pricing changes)
# ---------------------------------------------------------------------------

COST_PER_1M_INPUT_TOKENS  = 3.00
COST_PER_1M_OUTPUT_TOKENS = 15.00
AVG_TOKENS_PER_ENTRY_IN   = 800
AVG_TOKENS_PER_ENTRY_OUT  = 300


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def load_prompt_config(config: dict) -> dict:
    """Resolve prompt text from ``config['prompt_file']`` into ``config['system']``.

    *config* must contain at minimum ``model``, ``max_tokens``, and
    ``prompt_file`` (path to the system prompt .txt file).
    Returns an enriched config dict with a ``system`` key.
    """
    cfg = dict(config)
    prompt_path = Path(cfg.get("prompt_file", ""))
    if not prompt_path.is_absolute():
        # Resolve relative to repo root (three levels up from this file)
        repo_root = Path(__file__).resolve().parent.parent.parent
        prompt_path = repo_root / prompt_path
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    cfg["system"] = prompt_path.read_text(encoding="utf-8")
    return cfg


def load_prompt_config_from_json(json_path: str | Path) -> dict:
    """Load the legacy prompt.json format (has embedded 'system' string)."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Cost estimator
# ---------------------------------------------------------------------------

def estimate_cost(n_entries: int, batch_size: int = 5) -> dict:
    """Print and return an approximate cost estimate for the extraction run."""
    n_requests    = -(-n_entries // batch_size)
    input_tokens  = n_entries * AVG_TOKENS_PER_ENTRY_IN
    output_tokens = n_entries * AVG_TOKENS_PER_ENTRY_OUT
    input_cost    = (input_tokens  / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost   = (output_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    total_cost    = input_cost + output_cost

    print("=" * 45)
    print("COST ESTIMATE (approximate)")
    print("=" * 45)
    print(f"  Entries:        {n_entries:,}")
    print(f"  Batch size:     {batch_size}")
    print(f"  API requests:   ~{n_requests:,}")
    print(f"  Input tokens:   ~{input_tokens:,}  (${input_cost:.2f})")
    print(f"  Output tokens:  ~{output_tokens:,}  (${output_cost:.2f})")
    print(f"  Total estimate: ~${total_cost:.2f} USD")
    print("=" * 45)

    return {
        "n_entries":       n_entries,
        "n_requests":      n_requests,
        "total_cost_usd":  round(total_cost, 2),
    }


# ---------------------------------------------------------------------------
# Batch prompt builder
# ---------------------------------------------------------------------------

def _build_batch_prompt(entries: list) -> str:
    """Format multiple entries into a single user message."""
    lines = [
        f"Extract all {len(entries)} entries below. "
        f"Return a JSON array of {len(entries)} objects, one per entry, in order. "
        f"No markdown, no explanation, just the array.\n"
    ]
    for entry in entries:
        lines.append(f"[{entry['para_id']}] {entry['full_text']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------

def extract_batch(
    entries: list,
    prompt_config: dict,
    client: anthropic.Anthropic,
    retries: int = 5,
) -> list:
    """Extract structured fields from a batch of entries in one API call.

    Falls back to one-entry-at-a-time extraction if the batch response
    cannot be parsed.
    """
    system_prompt = prompt_config["system"]
    model         = prompt_config["model"]
    temperature   = prompt_config.get("temperature", 0)
    max_tokens    = min(prompt_config["max_tokens"] * len(entries), 8192)

    user_message = _build_batch_prompt(entries)
    raw_json     = None
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_json = response.content[0].text.strip()
            break
        except anthropic.RateLimitError as e:
            wait = min(2 ** attempt, 64)
            logger.warning("Rate limit (attempt %d/%d), waiting %ds", attempt, retries, wait)
            time.sleep(wait)
            last_error = e
        except anthropic.APIStatusError as e:
            wait = min(2 ** attempt, 64)
            logger.warning(
                "API error %d (attempt %d/%d), waiting %ds",
                e.status_code, attempt, retries, wait,
            )
            time.sleep(wait)
            last_error = e
        except anthropic.APIConnectionError as e:
            wait = min(2 ** attempt, 64)
            logger.warning("Connection error (attempt %d/%d), waiting %ds", attempt, retries, wait)
            time.sleep(wait)
            last_error = e

    if raw_json is None:
        logger.error(
            "Batch failed after %d attempts, falling back to individual extraction. "
            "Last error: %s",
            retries, last_error,
        )
        return [
            _error_record(e["para_id"], e["full_text"], str(last_error))
            for e in entries
        ]

    # Parse JSON response
    try:
        clean = raw_json
        # Strip markdown code fence if present
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = clean.rsplit("```", 1)[0]
        extracted_list = json.loads(clean.strip())

        if not isinstance(extracted_list, list):
            raise ValueError(f"Expected list, got {type(extracted_list).__name__}")
        if len(extracted_list) != len(entries):
            raise ValueError(
                f"Expected {len(entries)} results, got {len(extracted_list)}. "
                f"para_ids: {[e['para_id'] for e in entries]}"
            )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Batch parse error: %s — falling back to individual extraction", e)
        return [
            extract_batch([entry], prompt_config, client, retries)[0]
            for entry in entries
        ]

    return [
        _build_record(entries[i]["para_id"], entries[i]["full_text"], extracted_list[i])
        for i in range(len(entries))
    ]


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def _build_record(para_id: int, full_text: str, extracted: dict) -> dict:
    """Assemble a full pipeline record from the LLM's extracted dict."""
    rec: dict = {
        "para_id":           para_id,
        "full_text":         full_text,
        "homonym_index":     None,
        "variant_forms_raw": None,
    }
    for field in EXTRACTED_FIELDS:
        rec[field] = extracted.get(field, None)

    # Sanitise region_mentions
    if isinstance(rec.get("region_mentions"), list):
        rec["region_mentions"] = [
            {
                "informant": (r.get("informant") or ""),
                "county":    (r.get("county")    or ""),
            }
            for r in rec["region_mentions"]
            if isinstance(r, dict)
        ] or None

    # Normalise fullwidth Unicode in pronunciation fields
    for pron_field in ("pronunciation", "pronunciation_2", "pronunciation_3"):
        val = rec.get(pron_field)
        if val:
            rec[pron_field] = normalise_fullwidth(val)

    cov = check_coverage(rec)
    rec["coverage_pct"]       = cov["covered_pct"]
    rec["coverage_char_pct"]  = cov["coverage_char_pct"]
    rec["coverage_uncovered"] = cov["uncovered"] if cov["uncovered"] else None
    rec["parse_notes"]        = None
    rec["changed"]            = False
    rec["changed_fields"]     = []
    return rec


def _error_record(para_id: int, full_text: str, reason: str) -> dict:
    """Return an all-null record flagged as an extraction error."""
    rec = {f: None for f in EXTRACTED_FIELDS + PIPELINE_INJECTED}
    rec["para_id"]          = para_id
    rec["full_text"]        = full_text
    rec["entry_type"]       = "error"
    rec["parse_confidence"] = "low"
    rec["parse_notes"]      = reason
    rec["changed"]          = False
    rec["changed_fields"]   = []
    return rec


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch(
    sample: list,
    prompt_config: dict,
    client: anthropic.Anthropic,
    output_path: str | Path,
    batch_size: int = 5,
    rate_limit_delay: float = 2.0,
    checkpoint_every: int = 50,
    log_path: str | Path = "outputs/genai/extraction.log",
) -> list:
    """Run extraction over all entries in batches with checkpointing.

    Resumes automatically if *output_path* already contains partial results.
    """
    out     = Path(output_path)
    log_out = Path(log_path)
    ensure_dir(out.parent)
    ensure_dir(log_out.parent)

    fh = logging.FileHandler(log_out, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)

    results: list  = []
    done_ids: set  = set()
    if out.exists():
        with open(out, encoding="utf-8") as f:
            results = json.load(f)
        done_ids = {r["para_id"] for r in results}
        logger.info("Resuming: %d entries already done", len(done_ids))
        print(f"Resuming — {len(done_ids)} done, {len(sample) - len(done_ids)} remaining")

    todo    = [e for e in sample if e["para_id"] not in done_ids]
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    entries_done = 0

    with tqdm(total=len(sample), initial=len(done_ids), unit="entry", desc="Extracting") as pbar:
        for batch in batches:
            records = extract_batch(batch, prompt_config, client)
            for rec in records:
                results.append(rec)
                done_ids.add(rec["para_id"])
                entries_done += 1

            pbar.set_postfix({
                "last": f"{batch[-1]['para_id']} {batch[-1].get('headword_raw', '')[:12]}"
            })
            pbar.update(len(batch))
            time.sleep(rate_limit_delay)

            if entries_done % checkpoint_every == 0:
                save_json(out, results)
                logger.info("Checkpoint: %d/%d done", len(results), len(sample))

    save_json(out, results)
    logger.info("Batch complete: %d records → %s", len(results), output_path)
    print(f"\nDone. {len(results)} records saved → {output_path}")
    logger.removeHandler(fh)

    return results


# ---------------------------------------------------------------------------
# Entry-point helper (used by scripts/run_genai_parser.py)
# ---------------------------------------------------------------------------

def build_eligible_sample(rb_records: list) -> list:
    """Filter rule-based records to those eligible for LLM extraction."""
    return [
        r for r in rb_records
        if r.get("entry_type") not in ("cross_ref", "header")
        and r.get("parse_confidence") != "skip"
    ]
