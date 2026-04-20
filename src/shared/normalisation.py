"""
normalisation.py
================
Canonical normalisation utilities shared across rule-based parsing,
GenAI extraction, and evaluation.

All coverage stopwords and Unicode helpers live here; import from this
module rather than re-defining locally.
"""

import re
import math
import unicodedata
from difflib import SequenceMatcher


# ---------------------------------------------------------------------------
# Unicode normalisation
# ---------------------------------------------------------------------------

def normalise_fullwidth(s: str) -> str:
    """Map fullwidth Latin codepoints (U+FF01–U+FF5E) to ASCII equivalents.

    Source text sometimes contains fullwidth chars (ｄ U+FF44, ｔ U+FF54, etc.)
    in IPA transcriptions.  This normalises them before any string comparison
    or coverage calculation.
    """
    if not s:
        return s
    return "".join(
        chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c
        for c in s
    )


# Internal alias kept for backward compatibility with parse_entry imports.
_normalize_fullwidth = normalise_fullwidth


# ---------------------------------------------------------------------------
# Coverage stopwords
# ---------------------------------------------------------------------------

# Tokens that appear in full_text but are intentionally not stored in any
# structured field — excluding them from coverage_uncovered reduces noise.
# This is the authoritative set; do not duplicate in other modules.
COVERAGE_STOPWORDS: frozenset[str] = frozenset({
    "see", "also", "the", "and", "of", "in", "to", "for", "or", "as", "is",
    "an", "on", "at", "by", "it", "its", "from", "with", "this", "that",
    "was", "be", "are", "used", "who", "adds", "one", "he", "she", "his",
    "her", "they", "them", "their", "not", "no", "but", "if", "so", "up",
    # Source-structural markers
    "ir", "oe", "me", "dial", "phr", "cf", "lit", "obs", "ibid",
    "op", "cit", "ed", "eds", "vol", "pp", "sb", "sv", "id",
    # Common connectives
    "name", "affectionate", "gaa", "co", "games",
    "phrase", "word", "form", "use", "sense", "meaning",
    # POS alias tokens (long surface form vs stored abbreviation)
    "exclam", "interj", "excl",
    # POS-label fragments appearing in numbered-def text
    "pron", "part",
    # Usage/register labels sometimes inline but not always stored
    "colloq", "poss", "pronominal", "reflexive", "familiarly",
    # Variant-form prose markers
    "sometimes", "brack", "metathesis", "sickener",
    # Abbreviation meta-text
    "abbreviation",
    # Common prose tokens in no-pron paragraphs
    "commonly", "society",
})


# ---------------------------------------------------------------------------
# String flattening
# ---------------------------------------------------------------------------

def to_flat_string(value) -> str:
    """Flatten any field value (None, list, dict, str, numeric) to a plain string."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        if isinstance(value[0], dict):
            sorted_dicts = sorted(value, key=lambda d: str(list(d.values())[0]) if d else "")
            parts = [
                " ".join(sorted(str(v) for v in d.values() if v is not None))
                for d in sorted_dicts
            ]
            return " ".join(parts).strip()
        return " ".join(sorted(str(v) for v in value)).strip()
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values()).strip()
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else str(value)
    return str(value)


# ---------------------------------------------------------------------------
# Full normalisation pipeline
# ---------------------------------------------------------------------------

def normalise(value) -> str:
    """Full normalisation pipeline for metric comparison.

    Steps: flatten → fullwidth normalise → NFD decompose → strip combining
    marks → lowercase → remove non-word/non-space → collapse whitespace.
    Returns "" for empty/null.  Never raises.
    """
    try:
        s = to_flat_string(value)
        if not s:
            return ""
        s = normalise_fullwidth(s)
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = s.lower()
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s
    except Exception:
        return ""


def tokens(value) -> list[str]:
    """Return a list of normalised tokens from any field value."""
    n = normalise(value)
    return n.split() if n else []


# ---------------------------------------------------------------------------
# Similarity metrics
# ---------------------------------------------------------------------------

def exact_match(a, b) -> bool:
    """True if both values normalise to the same string."""
    return normalise(a) == normalise(b)


def ordered_similarity(a, b) -> float:
    """SequenceMatcher ratio on token lists (order-sensitive)."""
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return round(SequenceMatcher(None, ta, tb).ratio(), 4)


def unordered_similarity(a, b) -> float:
    """Token-set F1 overlap (order-insensitive)."""
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    precision = len(inter) / len(sb)
    recall = len(inter) / len(sa)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)
