"""Rule‑based parser for the Hiberno‑English dictionary.

This module contains a pure parser that attempts to extract structured
information from dictionary entry paragraphs using regular expressions and
heuristic rules. The parser is largely a direct refactoring of the
original notebook implementation but is organised into small, testable
functions. It makes no assumptions about I/O; instead, callers should
provide strings to parse and handle persistence externally.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional, Any

from ..shared.utils import clean_text


# ---------------------------------------------------------------------------
# Regular expressions and constants
#
# The POS_PAT pattern is used to identify part‑of‑speech abbreviations in
# the source text. It should be kept in sync with domain knowledge of
# permitted POS tags. Patterns are grouped using a non‑capturing group and
# separated by the pipe character.
POS_PAT = (
    r'(?:'
    r'personal pron\. |'
    r'reflexive pron\. |'
    r'pronominal phr\. |'
    r'pres\.part\. |'
    r'n\. phr\. |'
    r'n\.phr\. |'
    r'v\. phr\. |'
    r'v\.phr\. |'
    r'n\., v\. |'
    r'n\., adj\. |'
    r'n\. pl\. |'
    r'n\.pl\. |'
    r'v\. n\. |'
    r'v\.n\. |'
    r'interj\. |'
    r'exclam\. |'
    r'def\. art\. |'
    r'prep\. |'
    r'conj\. |'
    r'pron\. |'
    r'part\. |'
    r'int\. |'
    r'voc\. |'
    r'phr\. |'
    r'adj\. |'
    r'adv\. |'
    r'n\. |'
    r'v\. |'
    r'num\. |'
    r'excl\. '
    r')'
)


def normalize_entry_text(text: str) -> str:
    """Normalise entry text to a single line with consistent spacing.

    Replaces consecutive whitespace with a single space, ensures no
    extraneous spaces before punctuation and collapses slash notation.
    """
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    # fix slash patterns like "/, /"
    text = re.sub(r'/\s*,\s*/', '/, /', text)
    # remove spaces before punctuation
    text = re.sub(r'\s+([,.;:])', r'\1', text)
    return text


def extract_examples(text: str) -> List[str]:
    """Extract quoted examples from the text.

    Examples are enclosed in straight or curly double quotes. Returns
    a list of raw example strings without the quotes.
    """
    return [e.strip() for e in re.findall(r'[“\"](.*?)[”\"]', text) if e.strip()]


def extract_region_mentions(text: str) -> List[Dict[str, str]]:
    """Extract region mentions from the text.

    Region mentions are encoded as ``(CODE, Place)``. Each mention is
    returned as a dictionary with keys ``code`` and ``place``. If no
    mentions are found an empty list is returned.
    """
    mentions: List[Dict[str, str]] = []
    for m in re.finditer(r'\(([A-Z&]{1,5}|[A-Z][A-Za-z]+),\s*([A-Z][A-Za-z .-]+)\)', text):
        mentions.append({"code": m.group(1), "place": m.group(2)})
    return mentions


def split_definition_etymology(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Split a tail string into definition and etymology components.

    The definition and etymology are separated either by a leading ``<``
    marker or by the first ``<`` preceded by whitespace. If the text
    begins with ``<`` the definition is treated as missing. See the
    original notebook for details of the heuristic.
    """
    if not text:
        return None, None
    text = text.strip()
    # if text starts with < then only etymology is provided
    if text.startswith("<"):
        return None, text.lstrip("<").strip(" .;")
    # search for first < preceded by whitespace
    m = re.search(r'\s<\s*', text)
    if not m:
        # no etymology marker
        cleaned = text.strip(" .;")
        return cleaned or None, None
    left = text[:m.start()]
    right = text[m.end():]
    # attempt to stop etymology at the first example or cross reference
    stop_positions = []
    for pat in [r'[“\"]', r'\bSee\b']:
        m2 = re.search(pat, right)
        if m2:
            stop_positions.append(m2.start())
    if stop_positions:
        cut = min(stop_positions)
        etym = right[:cut].strip(" .;")
        tail = right[cut:].strip()
        definition = (left.strip(" .;") + ". " + tail).strip(" .;")
    else:
        etym = right.strip(" .;")
        definition = left.strip(" .;")
    return definition or None, etym or None


def split_cross_references(text: str) -> List[str]:
    """Split a semicolon‑delimited list of cross reference targets."""
    if not text:
        return []
    text = str(text).strip().rstrip(".")
    return [x.strip(" .;") for x in re.split(r'\s*;\s*', text) if x.strip(" .;")]


def parse_entry(text: str, idx: int) -> Dict[str, Any]:
    """Parse a single dictionary entry into a structured record.

    Parameters
    ----------
    text : str
        Raw paragraph text from the dictionary.
    idx : int
        Integer identifier for the entry; typically the paragraph number.

    Returns
    -------
    dict
        A dictionary containing the parsed fields. If parsing fails to
        confidently identify the structure, ``entry_type`` will be set to
        ``"unparsed"`` and the definition will contain the original text.

    Notes
    -----
    This function is intentionally verbose to mirror the heuristics of the
    original notebook. Each branch attempts to match a specific entry
    pattern. The order of checks is critical; do not reorder without
    understanding the downstream effects.
    """
    # start with a normalised version of the text
    original_text = str(text)
    text = normalize_entry_text(original_text)
    rec: Dict[str, Any] = {
        "para_id": idx,
        "id": f"hde_{idx:05d}",
        "source_text": text,
        "headword_raw": None,
        "headword": None,
        "variant_forms_raw": None,
        "variant_forms": [],
        "pronunciation": None,
        "pronunciation_2": None,
        "pronunciation_3": None,
        "pronunciation_4": None,
        "part_of_speech": None,
        "grammatical_labels": [],
        "definition": None,
        "etymology": None,
        "cross_references": [],
        "examples": extract_examples(text),
        "region_mentions": extract_region_mentions(text),
        "entry_type": "lexical",
        "parse_confidence": 0.5,
        "parse_notes": [],
    }
    # The remainder of this function is a direct transcription of the
    # original notebook logic. Each branch returns early on success.
    #
    # PURE CROSS‑REFERENCE ENTRIES
    m = re.match(
        r'^(?P<lemma>[^/]{1,140}?)\s*/(?P<pron>[^/]+?)/\s*,?\s*see\s+(?P<targets>.+?)(?:\.)?$',
        text,
        flags=re.I,
    )
    if m:
        lemma = m.group("lemma").strip(" ,.")
        targets_raw = m.group("targets").strip()
        rec["entry_type"] = "cross_reference"
        rec["headword_raw"] = lemma
        rec["headword"] = lemma.lower()
        rec["pronunciation"] = m.group("pron").strip()
        rec["cross_references"] = split_cross_references(targets_raw)
        rec["definition"] = None
        rec["parse_confidence"] = 1.0
        rec["parse_notes"] = ["Parsed as cross‑reference entry with pronunciation"]
        return rec
    # headword POS. see TARGET.
    m = re.match(
        rf'^(?P<lemma>[^/,.]{{1,140}}?)\s+(?P<pos>{POS_PAT})\s*see\s+(?P<targets>.+?)(?:\.)?$',
        text,
        flags=re.I,
    )
    if m:
        lemma = m.group("lemma").strip(" ,.")
        targets_raw = m.group("targets").strip()
        rec["entry_type"] = "cross_reference"
        rec["headword_raw"] = lemma
        rec["headword"] = lemma.lower()
        rec["part_of_speech"] = m.group("pos").strip()
        rec["cross_references"] = split_cross_references(targets_raw)
        rec["definition"] = None
        rec["parse_confidence"] = 1.0
        rec["parse_notes"] = ["Parsed as cross‑reference entry with POS"]
        return rec
    # headword, see TARGET.
    m = re.match(
        r'^(?P<lemma>[^,]{1,140}?)\s*,\s*see\s+(?P<targets>.+?)(?:\.)?$',
        text,
        flags=re.I,
    )
    if m:
        lemma = m.group("lemma").strip(" ,.")
        targets_raw = m.group("targets").strip()
        if (
            not re.search(POS_PAT, lemma, flags=re.I)
            and "/" not in lemma
            and ":" not in lemma
            and "“" not in lemma
            and '"' not in lemma
        ):
            rec["entry_type"] = "cross_reference"
            rec["headword_raw"] = lemma
            rec["headword"] = lemma.lower()
            rec["cross_references"] = split_cross_references(targets_raw)
            rec["definition"] = None
            rec["parse_confidence"] = 1.0
            rec["parse_notes"] = ["Parsed as cross‑reference entry"]
            return rec
    # headword, see.
    m = re.match(r'^(?P<lemma>.+?),\s*see\.?\$', text, flags=re.I)
    if m:
        rec["entry_type"] = "cross_reference"
        rec["headword_raw"] = m.group("lemma").strip(" ,.")
        rec["headword"] = rec["headword_raw"].lower()
        rec["cross_references"] = []
        rec["parse_confidence"] = 0.6
        rec["parse_notes"] = ["Incomplete cross‑reference target"]
        return rec
    # PHRASE / EXPRESSION LABEL ENTRIES
    m = re.match(
        rf'''
        ^(?P<lemma>[^/]+?)
        \s*/(?P<pron>[^/]+)/
        (?:\s+(?P<pos>{POS_PAT}))?
        \s*,\s*
        (?P<label>in\ the\ phrase|in\ the\ expression)
        \s+(?P<rest>.+)$
        ''',
        text,
        flags=re.I | re.X,
    )
    if m:
        lemma = m.group("lemma").strip()
        rec["headword_raw"] = lemma
        rec["headword"] = lemma.lower()
        rec["pronunciation"] = m.group("pron").strip()
        if m.group("pos"):
            rec["part_of_speech"] = m.group("pos").strip()
        rec["grammatical_labels"] = [m.group("label").strip().lower()]
        definition, etymology = split_definition_etymology(m.group("rest").strip())
        rec["definition"] = definition
        rec["etymology"] = etymology
        # extract cross references within the text
        rec["cross_references"] += [
            x.strip(" .)")
            for x in re.findall(r'(?:^|[.;]\s+|\(\s*)(?:See|see)\s+([A-Z][A-Z0-9 \-’\'.]+)', text)
        ]
        rec["parse_confidence"] = 0.96
        rec["parse_notes"] = ["Parsed as phrase/expression‑labelled entry"]
        return rec
    # fallback: no pronunciation, but phrase/expression‑labelled
    m = re.match(
        r'^(?P<lemma>[^,]{1,140}),\s*(?P<label>in the phrase|in the expression)\s*(?P<rest>.+)$',
        text,
        flags=re.I,
    )
    if m:
        rec["headword_raw"] = m.group("lemma").strip()
        rec["headword"] = rec["headword_raw"].lower()
        rec["grammatical_labels"] = [m.group("label").strip().lower()]
        definition, etymology = split_definition_etymology(m.group("rest").strip())
        rec["definition"] = definition
        rec["etymology"] = etymology
        rec["cross_references"] += [
            x.strip(" .)")
            for x in re.findall(r'(?:^|[.;]\s+|\(\s*)(?:See|see)\s+([A-Z][A-Z0-9 \-’\'.]+)', text)
        ]
        rec["parse_confidence"] = 0.90
        rec["parse_notes"] = ["Parsed as phrase/expression‑labelled entry"]
        return rec
    # GRAMMATICAL / USAGE NOTE ENTRIES
    m = re.match(r'^(?P<lemma>[^,/]{1,140}?)\s+are commonly used\s+(?P<rest>.+)$', text, flags=re.I)
    if m:
        rec["entry_type"] = "grammatical_note"
        rec["headword_raw"] = m.group("lemma").strip(" ,.")
        rec["headword"] = rec["headword_raw"].lower()
        rec["grammatical_labels"] = ["are commonly used"]
        rec["definition"] = m.group("rest").strip(" ,.")
        rec["parse_confidence"] = 0.82
        rec["parse_notes"] = ["Parsed as grammatical‑note entry"]
        return rec
    m = re.match(
        r'^(?P<lemma>[A-Z][A-Z0-9&.\'-]{1,20})\s+(?P<label>abbreviation for)\s+(?P<rest>.+)$',
        text,
        flags=re.I,
    )
    if m:
        rec["headword_raw"] = m.group("lemma").strip()
        rec["headword"] = rec["headword_raw"].lower()
        rec["grammatical_labels"] = [m.group("label").strip().lower()]
        rec["definition"] = m.group("rest").strip(" ,.")
        rec["parse_confidence"] = 0.95
        return rec
    # generic comma‑definition pattern
    m = re.match(r'^(?P<lemma>[^/]{1,140}?)(?:\s*\((?P<label>[^)]*)\))?,\s*(?P<rest>.+)$', text)
    if m:
        lemma = m.group("lemma").strip()
        rest = m.group("rest").strip()
        if not re.match(rf'^{POS_PAT}\b', rest):
            rec["headword_raw"] = lemma
            rec["headword"] = lemma.lower()
            if m.group("label"):
                rec["grammatical_labels"].append(m.group("label").strip())
            definition, etymology = split_definition_etymology(rest)
            rec["definition"] = definition
            rec["etymology"] = etymology
            rec["parse_confidence"] = 0.83
            rec["parse_notes"] = ["Parsed as comma‑definition entry"]
            return rec
    # repair malformed pronunciation delimiter (X /y?/ pos ...)
    m = re.match(r'^(?P<lemma>.+?)\s*/(?P<pron>[^/]+?)\?\s+(?P<rest>' + POS_PAT + r'.+)$', text)
    if m:
        repaired = f"{m.group('lemma')} /{m.group('pron').strip()}/ {m.group('rest')}"
        rec2 = parse_entry(repaired, idx)
        rec2["parse_notes"].append("Recovered malformed pronunciation closer")
        rec2["parse_confidence"] = max(rec2["parse_confidence"], 0.78)
        return rec2
    # pronunciation pattern with one or more pronunciations followed by POS
    m = re.match(r'^(?P<lemma>.+?)\s*/(?P<pron>[^/]+)/(?P<rest>.*)$', text)
    if m:
        left = m.group("lemma").strip()
        rest = m.group("rest").strip()
        rec["headword_raw"] = left
        hw = re.split(r'\s+also\s+|,\s*', left, maxsplit=1)[0].strip()
        rec["headword"] = hw.lower()
        if hw != left:
            rec["variant_forms_raw"] = left
            variants = [v.strip() for v in re.split(r'\s+also\s+|,\s*', left) if v.strip()]
            rec["variant_forms"] = [v for v in variants if v.lower() != rec["headword"]]
        rec["pronunciation"] = m.group("pron").strip()
        # collect extra pronunciations separated by comma slash patterns
        extra_prons: List[str] = []
        rest_for_prons = rest
        while True:
            m_extra = re.match(r'^\s*,\s*/([^/]+)/(?P<tail>.*)$', rest_for_prons)
            if not m_extra:
                break
            extra_prons.append(m_extra.group(1).strip())
            rest_for_prons = m_extra.group("tail").strip()
        if len(extra_prons) > 0:
            rec["pronunciation_2"] = extra_prons[0]
        if len(extra_prons) > 1:
            rec["pronunciation_3"] = extra_prons[1]
        if len(extra_prons) > 2:
            rec["pronunciation_4"] = extra_prons[2]
        rest = rest_for_prons.strip(" ,;")
        # look for variant prefix before POS, e.g. "also foo" in "left /pron/ also foo adj. ..."
        variant_prefix_match = re.match(rf'^(?P<variant_prefix>(?:also|sometimes also)\s+.*?)(?=\s+{POS_PAT}(?:\s|,|$))', rest, flags=re.I)
        if variant_prefix_match:
            variant_raw = variant_prefix_match.group("variant_prefix").strip()
            cleaned_variant_raw = re.sub(r'^(?:also|sometimes also)\s+', '', variant_raw, flags=re.I).strip()
            cleaned_variant_raw = re.sub(r'/[^/]+/', '', cleaned_variant_raw).strip(" ,;")
            cleaned_variant_raw = re.sub(r'\betc\.$', '', cleaned_variant_raw, flags=re.I).strip(" ,;")
            extra_variants = [v.strip(" .;,") for v in re.split(r',\s*|\s+or\s+', cleaned_variant_raw) if v.strip(" .;,")]
            rec["variant_forms_raw"] = (
                f"{rec['variant_forms_raw']}; {variant_raw}" if rec["variant_forms_raw"] else variant_raw
            )
            for v in extra_variants:
                if v and v.lower() != rec["headword"] and v not in rec["variant_forms"]:
                    rec["variant_forms"].append(v)
            rest = rest[variant_prefix_match.end():].lstrip(" ,;")
        sense_lead = None
        m_sense = re.match(r'^(?P<sense>\d+\.)\s*(?P<after>.+)$', rest)
        if m_sense:
            sense_lead = m_sense.group("sense")
            rest = m_sense.group("after").strip()
        rest = re.sub(
            r'^(adj|adv|prep|conj|pron|part|int|interj|voc|phr|n|v|num|excl|exclam)\s*,',
            r'\1.,',
            rest,
            flags=re.I,
        )
        pm = re.match(rf'^(?P<pos>{POS_PAT})(?:\s*\((?P<label>[^)]*)\))?(?P<after>.*)$', rest)
        if pm:
            rec["part_of_speech"] = pm.group("pos").strip()
            if pm.group("label"):
                rec["grammatical_labels"].append(pm.group("label").strip())
            after = pm.group("after").lstrip(" ,")
            rec["parse_confidence"] = 0.90
        else:
            after = rest
            rec["parse_notes"].append("POS not confidently parsed")
            rec["parse_confidence"] = 0.72
        definition, etymology = split_definition_etymology(after)
        if definition and sense_lead:
            definition = f"{sense_lead} {definition}"
        rec["definition"] = definition
        rec["etymology"] = etymology
        rec["cross_references"] += [
            x.strip(" .)")
            for x in re.findall(r'(?:^|[.;]\s+|\(\s*)(?:See|see)\s+([A-Z][A-Z0-9 \-’\'.]+)', text)
        ]
        return rec
    # POS with no pronunciation
    m = re.match(r'^(?P<lemma>[^/]{1,120}?)\s+(?P<rest>' + POS_PAT + r'.+)$', text)
    if m:
        rec["headword_raw"] = m.group("lemma").strip()
        rec["headword"] = rec["headword_raw"].lower()
        rest = m.group("rest").strip()
        rest = re.sub(
            r'^(adj|adv|prep|conj|pron|part|int|interj|voc|phr|n|v|num|excl|exclam)\s*,',
            r'\1.,',
            rest,
            flags=re.I,
        )
        pm = re.match(rf'^(?P<pos>{POS_PAT})(?:\s*\((?P<label>[^)]*)\))?(?P<after>.*)$', rest)
        if pm:
            rec["part_of_speech"] = pm.group("pos").strip()
            if pm.group("label"):
                rec["grammatical_labels"].append(pm.group("label").strip())
            definition, etymology = split_definition_etymology(pm.group("after").lstrip(" ,"))
            rec["definition"] = definition
            rec["etymology"] = etymology
            rec["parse_confidence"] = 0.78
            return rec
    # variant without pronunciation
    m = re.match(r'^(?P<lemma>[^/]{1,120}?)\s+also\s+(?P<variant>[^/]{1,120}?)\s+(?P<rest>.+)$', text, flags=re.I)
    if m:
        rec["headword_raw"] = m.group("lemma").strip()
        rec["headword"] = rec["headword_raw"].lower()
        rec["variant_forms_raw"] = f"{m.group('lemma').strip()} also {m.group('variant').strip()}"
        rec["variant_forms"] = [m.group("variant").strip()]
        definition, etymology = split_definition_etymology(m.group("rest").strip())
        rec["definition"] = definition
        rec["etymology"] = etymology
        rec["parse_confidence"] = 0.74
        rec["parse_notes"] = ["Parsed as variant‑without‑pronunciation entry"]
        return rec
    # malformed pronunciation delimiter (X y/ pos ...)
    m = re.match(r'^(?P<lemma>.+?)\s+(?P<pron>[^ ]+/)\s*(?P<rest>.+)$', text)
    if m:
        repaired = f"{m.group('lemma')} /{m.group('pron').rstrip('/').strip()}/ {m.group('rest')}"
        rec2 = parse_entry(repaired, idx)
        rec2["parse_notes"].append("Recovered malformed pronunciation delimiter")
        rec2["parse_confidence"] = max(rec2["parse_confidence"], 0.75)
        return rec2
    # default fallback
    rec["entry_type"] = "unparsed"
    rec["headword_raw"] = text.split(" ", 1)[0]
    rec["headword"] = rec["headword_raw"].lower()
    rec["definition"] = original_text
    rec["parse_notes"].append("Could not confidently parse entry structure")
    rec["parse_confidence"] = 0.2
    return rec


def parse_entries(entries: List[str]) -> List[Dict[str, Any]]:
    """Parse a list of raw dictionary entries.

    Parameters
    ----------
    entries : list of str
        A list of raw entry strings. The index of each entry in the list
        is used as the ``para_id`` in the returned records.

    Returns
    -------
    list of dict
        A list of parsed records as returned by :func:`parse_entry`.
    """
    records: List[Dict[str, Any]] = []
    for idx, text in enumerate(entries, start=1):
        record = parse_entry(text, idx)
        records.append(record)
    return records
