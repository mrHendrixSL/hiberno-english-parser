r"""
parser.py  (v7)
===============
Core rule-based parsing logic for A Dictionary of Hiberno-English.

Version history is preserved here for traceability:

v3 fixes
--------
  F1.  POS comma-variants: accept 'adj,' 'n,' 'v,' in addition to 'adj.' etc.
  F2.  POS dual tokens: 'n., adj.' — consume second POS token before body starts
  F3.  See X. stripped from definition and examples after cross_references extracted
  F4.  CITATION regex extended; is_inside_parens guard added
  F5.  Redirect-only detection generalised
  F6.  Region extraction loosened: '(SOM, Kerry, who adds: ...)' handled
  F7.  Region deduplication
  F8.  POS token stripped from headword_raw for no-pron entries
  F9.  Fullwidth Unicode chars normalised to ASCII in pronunciation fields

v4 fixes
--------
  F10. Multi-POS storage: secondary POS tokens merged into part_of_speech
  F11. Compound POS with space: 'n. phr.', 'n. pl.', etc. recognised
  F12. Extended POS vocabulary
  F13. No-pron body extraction
  F14. word-boundary guard on body_m
  F15. Coverage stopwords extended
  F16. POS vocabulary extended

v5 fixes
--------
  G1.  POS ordering: 'voc' moved before 'v'
  G2.  Etymology hard-stop after '< X.'
  G3.  Examples strip trailing etymology
  G4.  Definition boundary: double-quoted inline glosses no longer trigger it
  G5.  Stringified list examples joined with '; '
  G6.  Definition truncated at 'phr' marker — guard tightened
  G7.  Variant forms: region parentheticals stripped
  G8.  Redirect misclassification fixed
  G9.  Missing definition: salvage from etymology prose
  G10. POS stored as list when multiple labels present

v6 fixes
--------
  H1.  HE_EXAMPLE extended: comma triggers boundary before uppercase quote
  H2.  who_adds examples preserved to examples field
  H3.  ETYMOLOGY_IN_DEFINITION rescue
  H4.  VARIANT_NOT_SPLIT for phrase headwords
  H5.  MISCLASSIFIED_REDIRECT / CROSS_REF_NOT_EXTRACTED
  H6.  ETYMOLOGY_TRUNCATED fixed

v7 fixes  (from full row-level audit)
--------------------------------------
  I1.  ETYM_IN_EXAMPLES: two post-hoc patterns strip etymology from examples
  I2.  MISSING_DEFINITION: extended _salvage_def_from_etym
  I3.  VARIANT_NOT_SPLIT for no-pron entries
  I4.  POS_MISSING in no-pron entries: improved scan
"""

import re

from src.shared.normalisation import normalise_fullwidth as _normalize_fullwidth
from src.shared.normalisation import COVERAGE_STOPWORDS as _COVERAGE_STOPWORDS
from src.shared.schema import COVERAGE_FIELDS_RB as _COVERAGE_FIELDS


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

ETYM_START = re.compile(
    r'(?<![(\w])<\s*(?:Ir|OE|ME|E dial|E\b|Fr\b|L\b|ON\b|Scots\b|W\b|Gael\b)'
)

# I1a: Etymology embedded mid-examples
ETYM_EMBEDDED = re.compile(
    r'\s+(<\s*(?:Ir|OE|ME|E dial|E\b|Fr\b|L\b|ON\b|Scots\b|W\b|Gael\b|OF\b|Du\b|M\b)'
    r'[^<"\'\u2018\u2019\u201c\u201d\n]*?\.)',
    re.DOTALL
)

# I1b: Bare etymology marker at end of examples with no terminating period
ETYM_TRAILING_BARE = re.compile(
    r'\s+(<\s*(?:Ir|OE|ME|E dial|E\b|Fr\b|L\b|ON\b|Scots\b|W\b|Gael\b|OF\b|Du\b)'
    r'(?:\s+\w[^<\u201c\u201d"\n]{0,40})?)\s*$'
)

# G2: Complete short etymology followed by a quote or paren
ETYM_HARD_STOP = re.compile(
    r'(<\s*(?:Ir|OE|ME|E dial|E\b|Fr\b|L\b|ON\b|Scots\b|W\b|Gael\b)'
    r'[^<\'\u2018\u201c\n]*?\.)\s+(?=[\'"\u2018\u201c\(])'
)

# H1: Single-quoted HE usage example boundary
HE_EXAMPLE = re.compile(r"[.;]\s+[\u2018']|,\s+[\u2018'][A-Z\u00C0-\u024F]")

# Literary citation
CITATION = re.compile(
    r'[.;]\s+[A-Z][a-zA-Z\u00C0-\u024F\u2018\u2019\-\s]+?,\s+'
    r'[A-Z\u2018][^\n,]{5,},\s+(?:\d|act\b|vol\b|ch\b)'
)

# Region tag: (ABBR, County)
REGION_PAT = re.compile(r'\(([A-Z]{1,4}),\s*([A-Za-z][a-zA-Z\s]*?)(?=[,;).])')

# See X. extraction
SEE_PAT = re.compile(
    r'\b[Ss]ee\s+([A-Z\u00C0-\u024F][A-Z0-9\s\'\u2018\u2019\-;:,()\u00C0-\u024F]+?)'
    r'(?=\s*\.|(?:\s*[;,])?\s*[a-z]|\s*$)'
)

# See X. strip from field text
SEE_STRIP = re.compile(
    r'\.?\s*\b[Ss]ee\s+[A-Z\u00C0-\u024F][A-Z0-9\s\'\u2018\u2019\-;:,()\u00C0-\u024F]+?'
    r'(?=\s*\.|(?:\s*[;,])?\s*[a-z]|$)\.*\s*$'
)

# Redirect-only detection (G8, H5)
REDIRECT_PAT = re.compile(
    r'^([^.,(]{1,60}(?:,\s+[^.,(]{1,40})?)'
    r'(?:\s*/[^/]+/)?\s*'
    r'[.,]?\s+[Ss]ee\s+'
    r'([A-Z\u00C0-\u024F][A-Z0-9\s\'\u2018\u2019\-;,()\u00C0-\u024F]+?'
    r'|[a-z\u00C0-\u024F]\w+)\.*\s*$'
)

SINGLE_LTR = re.compile(r"^[A-Z]'?$")
PRON_PAT   = re.compile(r'/([^/]+)/')
PRON_SPAN  = re.compile(r'/[^/]+/')

POS_CORE = (
    r'n\. phr|n\. pl|adv\. phr|v\. phr|adj\. phr|v\. n|p\. part|pres\. part|v\. part|v\. imp|'
    r'n\.phr|n\.pl|adv\.phr|v\.phr|adj\.phr|v\.n|p\.part|pres\.part|'
    r'v\.imp|v\.part|n\.v|vn|'
    r'reflexive pron|personal pron|possessive adj|pronominal phr|verbal n|indefinite article|def\. art|'
    r'place-name|'
    r'num|n|adj|adv|voc|v|phr|interj|int|conj|pron|'
    r'exclam|excl|prep|imp|pl|pers|part|interrogative|'
    r'acronym|prefix|suffix|poss'
)

POS_TOKENS        = r'(?:' + POS_CORE + r')(?:[.,]?)'
POS_TOKENS_STRICT = r'(?:' + POS_CORE + r')(?:[.,])'

POS_PAT        = re.compile(POS_TOKENS)
POS_PAT_STRICT = re.compile(POS_TOKENS_STRICT)
ALSO_SKIP  = re.compile(r'\s*also\s+.+?(?=(?:' + POS_TOKENS_STRICT + r'))', re.DOTALL)
ALSO_PAT   = re.compile(r'/[^/]+/\s+also\s+(.+?)\s+(?=' + POS_TOKENS_STRICT + r')', re.DOTALL)
HW_PAT     = re.compile(r'^(.+?)\s*/[^/]+/')

NUM_STRIP  = re.compile(
    r'^\d+\.\s*(?:Also\s+\S+\s+)?(?:' + POS_TOKENS_STRICT + r')(?:\s*\([^)]+\))?[,.]?\s*'
)

WHO_ADDS_STRIP   = re.compile(r',?\s*who adds:[^)]*\)?', re.IGNORECASE)
WHO_ADDS_EXTRACT = re.compile(
    r",?\s*who adds:\s*['\u2018]([^'\u2019]{5,})['\u2019]?[^)]*\)?",
    re.IGNORECASE
)

ORPHAN_PAREN = re.compile(r'\s+\)')

TRAILING_ETYM_SAFE = re.compile(
    r'\s*(?:<\s*(?:Ir|OE|ME|E dial|E\b|Fr\b|L\b|ON\b|Scots\b|W\b|Gael\b|OF\b)'
    r'[^<\u201c\u201d"]*?)+\.\s*$',
    re.DOTALL
)

TRAILING_POS = re.compile(
    r'\s+(?:n|adj|v|adv|phr|int|interj|voc|conj|pron|excl|exclam|prep|imp|pl)[.,]?$'
)

# Module-level POS label regex — eliminates the duplicate inline definition
# that previously appeared inside _split_body() in two places.
_POS_LABEL_RE = re.compile(
    r'^(?:num|n|adj|adv|voc|v|phr|interj|int|conj|pron|excl|exclam|prep'
    r'|imp|pl|pers|part|pres\.part|p\.part|v\.part|v\.n|n\.phr|n\.pl'
    r'|adv\.phr|v\.phr|adj\.phr|pres\. part|p\. part|v\. part|v\. n'
    r'|n\. phr|n\. pl|adv\. phr|v\. phr|place-name|def\. art|suffix'
    r'|prefix|acronym|verbal n|pronominal phr|possessive adj'
    r'|personal pron|reflexive pron)\.*\s*$',
    re.I
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_header_pron_end(text: str) -> int:
    """End position after last consecutive headword-adjacent /pron/ block."""
    last_end = 0
    for m in PRON_SPAN.finditer(text):
        if last_end and m.start() - last_end > 6:
            break
        last_end = m.end()
    return last_end


def _is_inside_parens(text: str, pos: int) -> bool:
    """Return True if *pos* is inside unmatched parentheses."""
    depth = 0
    for i in range(pos):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth = max(0, depth - 1)
    return depth > 0


_PHR_BEFORE = re.compile(r'(?:adv|v|n|adj)?\.?\s*phr\.?\s*$|adv\.phr\s*$', re.I)


def _first_example_boundary(body: str):
    """Return position of the first genuine example/citation boundary.

    Skips HE_EXAMPLE matches inside parentheses (F4) and after phrase
    markers (G11).
    """
    candidates = []

    for m in HE_EXAMPLE.finditer(body):
        if _is_inside_parens(body, m.start()):
            continue
        if _PHR_BEFORE.search(body[:m.start()]):
            continue
        after_match = body[m.end():]
        if (m.group(0).startswith(',')
                and re.match(r'[^\'\u2019]{3,}[\[]', after_match)):
            continue
        candidates.append(m.start())
        break

    ci_m = CITATION.search(body)
    if ci_m:
        candidates.append(ci_m.start())

    return min(candidates) if candidates else None


def _salvage_def_from_etym(definition: str, etymology: str) -> str:
    """G9 / I2: salvage a definition from explanatory prose inside etymology."""
    if definition:
        return definition
    # G9 / I2c: comma-separated prose
    def_m = re.search(
        r'<\s*\w[^,<>\"\']{1,30},\s+([a-z][^<\u2018\u2019\'"]{8,}?)(?:\.|$)',
        etymology
    )
    if def_m:
        cand = def_m.group(1).strip().rstrip('.').strip()
        if len(cand) >= 8 and not re.search(r'^[A-Z]', cand):
            return cand
    # I2a: semicolon-separated prose
    semi_m = re.search(r';\s+([a-z][^<\u2018\u2019\'"]{8,}?)(?:\.|$)', etymology)
    if semi_m:
        cand = semi_m.group(1).strip().rstrip('.').strip()
        if len(cand) >= 8 and not re.search(r'^[A-Z]', cand):
            return cand
    # I2b: period then prose gloss
    period_m = re.search(
        r'<\s*\w[^.]{0,20}\.\s+([A-Za-z\'\u2018\u2019][^<\u201c"]{8,}?)(?:\.|$)',
        etymology
    )
    if period_m:
        cand = period_m.group(1).strip().rstrip('.').strip()
        if len(cand) >= 8 and not re.match(r'^[\'"\u2018\u2019\u201c]', cand):
            return cand
    # I2d: quoted gloss after comma
    gloss_m = re.search(
        r'<\s*\w[^,<>\"\']{1,30},\s+[\u2018\']([^\u2019\'\"]{6,})[\u2019\']',
        etymology
    )
    if gloss_m:
        cand = gloss_m.group(1).strip()
        if len(cand) >= 6:
            return cand
    return definition


def _split_body(body: str):
    """Split body into (definition, etymology, examples_raw).

    G2: Uses ETYM_HARD_STOP when a complete etymology is followed by a quote.
    G3: TRAILING_ETYM_SAFE strips trailing etymology from examples in all paths.
    """
    hard_m = ETYM_HARD_STOP.search(body)
    etym_m = ETYM_START.search(body)
    ex_start = _first_example_boundary(body)

    def _promote_trailing_etym(etymology, examples_raw):
        if examples_raw and not etymology:
            trail = TRAILING_ETYM_SAFE.search(examples_raw)
            if trail:
                etymology    = trail.group(0).strip()
                examples_raw = examples_raw[:trail.start()].strip() or ''
        return etymology, examples_raw

    if hard_m and etym_m and hard_m.start() >= etym_m.start():
        etym_end     = hard_m.start() + len(hard_m.group(1))
        definition   = body[:etym_m.start()].strip().rstrip(',')
        etymology    = body[etym_m.start():etym_end].strip()
        examples_raw = body[etym_end:].strip()
        etymology, examples_raw = _promote_trailing_etym(etymology, examples_raw)
        definition   = _salvage_def_from_etym(definition, etymology)

    elif etym_m and ex_start is not None:
        etym_start = etym_m.start()
        if ex_start <= etym_start:
            definition   = body[:ex_start + 1].strip().rstrip(',')
            etymology    = ''
            examples_raw = body[ex_start + 2:].strip()
            etymology, examples_raw = _promote_trailing_etym(etymology, examples_raw)
        else:
            etym_body     = body[etym_start:]
            etym_has_sent = re.search(r'[.;]\s+[\'"\u2018\u201c]', etym_body)
            if etym_has_sent:
                definition   = body[:etym_start].strip().rstrip(',')
                etymology    = body[etym_start:ex_start + 1].strip()
                examples_raw = body[ex_start + 2:].strip()
            else:
                definition   = body[:etym_start].strip().rstrip(',')
                etymology    = etym_body.strip()
                examples_raw = ''
            if examples_raw:
                trail = TRAILING_ETYM_SAFE.search(examples_raw)
                if trail:
                    examples_raw = examples_raw[:trail.start()].strip() or ''
            if not definition or _POS_LABEL_RE.match(definition):
                definition = _salvage_def_from_etym('', etymology)

    elif etym_m:
        definition   = body[:etym_m.start()].strip().rstrip(',')
        etymology    = body[etym_m.start():].strip()
        examples_raw = ''
        if not definition or _POS_LABEL_RE.match(definition):
            definition = _salvage_def_from_etym('', etymology)
        else:
            definition = _salvage_def_from_etym(definition, etymology)

    elif ex_start is not None:
        definition   = body[:ex_start + 1].strip()
        etymology    = ''
        examples_raw = body[ex_start + 2:].strip()
        etymology, examples_raw = _promote_trailing_etym(etymology, examples_raw)

    else:
        definition   = body.strip()
        etymology    = ''
        examples_raw = ''

    return definition, etymology, examples_raw


def _clean_def(d: str):
    """Strip region tags, leading number prefix, trailing stray punctuation.

    Returns ``(cleaned_def, who_adds_example_or_None)``.
    """
    if not d:
        return None, None
    who_m       = WHO_ADDS_EXTRACT.search(d)
    who_example = who_m.group(1).strip() if who_m else None
    d = REGION_PAT.sub('', d)
    d = WHO_ADDS_STRIP.sub('', d)
    d = ORPHAN_PAREN.sub('', d)
    d = re.sub(r'^\d+\.\s*', '', d)
    d = re.sub(r'\s{2,}', ' ', d).strip()
    d = re.sub(r'\s+[.;,]+$', '', d).strip()
    d = d.strip(',').strip(';').strip()
    return (d or None), who_example


def _strip_see(text: str) -> str:
    """F3: remove trailing 'See X.' from a field string."""
    if not text:
        return text
    return SEE_STRIP.sub('', text).strip().rstrip('.').strip()


def _extract_region_mentions(text: str):
    """F6/F7: extract ``(informant, county)`` pairs."""
    tags = [
        {'informant': a, 'county': b.strip()}
        for a, b in REGION_PAT.findall(text)
    ]
    return tags or None


def _dedup_regions(regions):
    """F7: deduplicate region mentions preserving order."""
    if not regions:
        return regions
    seen, result = set(), []
    for r in regions:
        key = (r['informant'], r['county'])
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def _extract_see_refs(text: str):
    """Extract all ``See X`` targets as a list."""
    refs = []
    for m in SEE_PAT.finditer(text):
        for r in re.split(r'[;,]', m.group(1)):
            r = r.strip()
            if r:
                refs.append(r)
    return refs or None


# ---------------------------------------------------------------------------
# Coverage helpers
# ---------------------------------------------------------------------------

_CHAR_FIELDS = [
    'headword_raw', 'variant_forms_raw', 'pronunciation', 'pronunciation_2',
    'pronunciation_3', 'part_of_speech', 'grammatical_labels', 'definition',
    'etymology', 'examples', 'cross_references',
]


def _field_tokens(value) -> set:
    """Extract normalised word tokens from any field value type."""
    if value is None:
        return set()
    if isinstance(value, list):
        text = ' '.join(
            v if isinstance(v, str)
            else (v.get('informant', '') + ' ' + v.get('county', ''))
            if isinstance(v, dict)
            else str(v)
            for v in value
        )
    elif isinstance(value, dict):
        text = ' '.join(str(v) for v in value.values())
    else:
        text = str(value)
    text = _normalize_fullwidth(text)
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return set(text.split())


def check_coverage(record: dict) -> dict:
    """Check what fraction of full_text tokens and characters are captured.

    Returns a dict with keys:
      covered_pct       float | None
      coverage_char_pct float | None
      uncovered         list[str]
      field_tokens      dict[str, int]
    """
    full_text = record.get('full_text', '') or ''
    if not full_text:
        return {
            'covered_pct': None, 'coverage_char_pct': None,
            'uncovered': [], 'field_tokens': {},
        }

    ft_stripped = re.sub(
        r",?\s*who adds:\s*[\u2018'][^\u2019']*[\u2019']?[^)]*\)?",
        '', full_text, flags=re.IGNORECASE
    )
    ft_normalised = _normalize_fullwidth(ft_stripped)
    raw_tokens = set(re.sub(r'[^\w\s]', ' ', ft_normalised.lower()).split())
    src_tokens = {
        t for t in raw_tokens
        if len(t) > 2 and not t.isdigit() and t not in _COVERAGE_STOPWORDS
    }

    all_parsed: set = set()
    field_tokens: dict = {}
    for field in _COVERAGE_FIELDS:
        ft = _field_tokens(record.get(field))
        field_tokens[field] = len(ft)
        all_parsed |= ft

    if src_tokens:
        uncovered_raw = src_tokens - all_parsed
        uncovered = sorted(
            t for t in uncovered_raw
            if len(t) > 3 and not t.startswith(('0x', '\\u'))
        )
        covered_pct = round(
            100.0 * (len(src_tokens) - len(uncovered_raw)) / len(src_tokens), 1
        )
    else:
        uncovered   = []
        covered_pct = 100.0

    def _field_chars(val):
        if val is None:
            return 0
        if isinstance(val, list):
            return sum(len(str(v)) for v in val)
        return len(str(val))

    content_chars     = sum(_field_chars(record.get(f)) for f in _COVERAGE_FIELDS)
    coverage_char_pct = min(100.0, round(100.0 * content_chars / len(full_text), 1))

    return {
        'covered_pct':       covered_pct,
        'coverage_char_pct': coverage_char_pct,
        'uncovered':         uncovered,
        'field_tokens':      field_tokens,
    }


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_entry(para_id: int, text: str) -> dict:
    """Parse one raw paragraph into a structured record."""
    notes = []
    rec = dict(
        para_id=para_id,
        full_text=text,
        entry_type='full',
        headword_raw=None,
        headword=None,
        homonym_index=None,
        variant_forms_raw=None,
        variant_forms=None,
        pronunciation=None,
        pronunciation_2=None,
        pronunciation_3=None,
        part_of_speech=None,
        grammatical_labels=None,
        definition=None,
        etymology=None,
        cross_references=None,
        examples=None,
        region_mentions=None,
        parse_confidence='high',
        parse_notes=None,
        coverage_pct=None,
        coverage_char_pct=None,
        coverage_uncovered=None,
    )

    # ── 1. Section header ────────────────────────────────────────────────────
    if SINGLE_LTR.match(text.strip()):
        rec['entry_type']       = 'header'
        rec['parse_confidence'] = 'skip'
        return rec

    # ── 2. Redirect-only ─────────────────────────────────────────────────────
    prons = PRON_PAT.findall(text)
    rd_m  = REDIRECT_PAT.match(text.strip())
    if rd_m and not prons:
        rec['entry_type']   = 'cross_ref'
        rec['headword_raw'] = rd_m.group(1).strip()
        _hw_cr  = TRAILING_POS.sub('', rd_m.group(1).strip()).strip()
        _hom    = re.match(r'^(.{2,}?)(\d+)$', _hw_cr)
        if _hom and not re.search(r'\s', _hom.group(1).rstrip()):
            rec['headword']      = _hom.group(1).strip().lower()
            rec['homonym_index'] = int(_hom.group(2))
        else:
            rec['headword']      = _hw_cr.lower()
            rec['homonym_index'] = None
        targets = [t.strip() for t in re.split(r'[;,]', rd_m.group(2)) if t.strip()]
        rec['cross_references'] = targets
        cov = check_coverage(rec)
        rec['coverage_pct']       = cov['covered_pct']
        rec['coverage_char_pct']  = cov['coverage_char_pct']
        rec['coverage_uncovered'] = cov['uncovered'] if cov['uncovered'] else None
        return rec

    # ── 3. No pronunciation → low confidence, extract body anyway ────────────
    if not prons:
        hw_m = HW_PAT.match(text)
        if hw_m:
            hw_raw = hw_m.group(1).strip()
        else:
            _pos_scan = re.search(r'(?<!\w)(?:' + POS_TOKENS_STRICT + r')', text)
            if _pos_scan:
                hw_raw = text[:_pos_scan.start()].strip().rstrip(',')
            else:
                _comma_30 = re.search(r',(?=\s)', text[:30])
                if _comma_30:
                    hw_raw = text[:_comma_30.start()].strip()
                else:
                    _first_space = text.find(' ')
                    hw_raw = text[:_first_space].strip() if _first_space > 0 else text[:40].strip()

        hw_raw = TRAILING_POS.sub('', hw_raw).strip()

        _I3_ADJ = re.compile(
            r'(?:ing|ive|ary|ory|ive|ising|izing|ful|less|ent|ant|ual|ive)$', re.I
        )
        np_vf = None
        if ',' in hw_raw:
            np_parts = [p.strip() for p in hw_raw.split(',')]
            np_first = np_parts[0]
            np_rest  = [p for p in np_parts[1:] if p]
            rest_joined      = ', '.join(np_rest)
            rest_has_pos     = bool(POS_PAT_STRICT.search(rest_joined))
            any_multiword    = any(' ' in r for r in np_rest)
            rest_is_article  = (len(np_rest) == 1 and len(np_rest[0]) <= 5
                                and np_rest[0][:1].isupper())
            rest_is_qualifier = (len(np_rest) == 1
                                 and bool(_I3_ADJ.search(np_rest[0])))
            if (np_rest and ' ' not in np_first
                    and not all(p.lower() == np_first.lower() for p in np_rest)
                    and not re.search(r'[.(<]', rest_joined)
                    and not rest_has_pos
                    and not any_multiword
                    and not rest_is_article
                    and not rest_is_qualifier):
                hw_raw = np_first
                np_vf  = np_rest

        rec['headword_raw']     = hw_raw
        rec['headword']         = re.sub(r'\d+$', '', hw_raw).strip().lower()
        if np_vf:
            rec['variant_forms_raw'] = ', '.join(np_vf)
            rec['variant_forms']     = np_vf
        rec['parse_confidence'] = 'low'
        rec['region_mentions']  = _dedup_regions(_extract_region_mentions(text))
        rec['cross_references'] = _extract_see_refs(text)
        notes.append('no pronunciation found')

        hw_end   = hw_m.end() if hw_m else len(rec['headword_raw'])
        after_hw = text[hw_end:].lstrip()

        pos_m_nopron = POS_PAT.match(after_hw.lstrip(' ,'))
        if not pos_m_nopron:
            _np_pos_scan = re.search(
                r'(?<!\w)(?:' + POS_TOKENS_STRICT + r')',
                after_hw[:40]
            )
            if _np_pos_scan:
                preceding = after_hw[:_np_pos_scan.start()].strip().rstrip(',')
                if not preceding or re.search(r'^[,\s]*$', preceding):
                    pos_m_nopron = POS_PAT_STRICT.match(
                        after_hw[_np_pos_scan.start():]
                    )
                    if pos_m_nopron:
                        after_hw = after_hw[_np_pos_scan.start():]

        if pos_m_nopron:
            rec['part_of_speech'] = pos_m_nopron.group(0).rstrip('.,').lstrip(' ,')
            after_hw = after_hw[
                after_hw.index(pos_m_nopron.group(0)) + len(pos_m_nopron.group(0)):
            ].lstrip(' ,')
            extra_pos_np = []
            rem_np = after_hw
            while True:
                m2np = POS_PAT_STRICT.match(rem_np.lstrip())
                if m2np:
                    extra_pos_np.append(m2np.group(0).rstrip('.,'))
                    rem_np = rem_np.lstrip()[m2np.end():].lstrip(' ,')
                else:
                    break
            if extra_pos_np:
                rec['part_of_speech'] = [rec['part_of_speech']] + extra_pos_np
                after_hw = rem_np
            gl_m_np = re.match(r'\s*\(([^)]{2,40})\)', after_hw)
            if gl_m_np and not rec['grammatical_labels']:
                rec['grammatical_labels'] = gl_m_np.group(1)
            rec['parse_confidence'] = 'medium'
            notes[-1] = 'no pronunciation found'

        if after_hw.strip():
            d_np, e_np, ex_np = _split_body(after_hw.strip())
            if ex_np and not e_np:
                etym_trail = TRAILING_ETYM_SAFE.search(ex_np)
                if etym_trail:
                    e_np  = etym_trail.group(0).strip()
                    ex_np = ex_np[:etym_trail.start()].strip() or None
            cd_np, who_ex_np = _clean_def(d_np)
            rec['definition'] = cd_np
            if who_ex_np:
                ex_np = (ex_np + '; ' + who_ex_np) if ex_np else who_ex_np
            rec['etymology']  = e_np or None
            rec['examples']   = ex_np or None
            if rec['definition'] and isinstance(rec['definition'], str):
                rec['definition'] = _strip_see(rec['definition']) or rec['definition']
            rec['cross_references'] = _extract_see_refs(text)

        rec['parse_notes'] = '; '.join(notes)
        cov = check_coverage(rec)
        rec['coverage_pct']       = cov['covered_pct']
        rec['coverage_char_pct']  = cov['coverage_char_pct']
        rec['coverage_uncovered'] = cov['uncovered'] if cov['uncovered'] else None
        return rec

    # ── 4. Headword ──────────────────────────────────────────────────────────
    hw_m = HW_PAT.match(text)
    rec['headword_raw'] = hw_m.group(1).strip() if hw_m else None

    hw_raw_v6 = rec['headword_raw'] or ''
    if ',' in hw_raw_v6 and not rec.get('variant_forms_raw'):
        parts = [p.strip() for p in hw_raw_v6.split(',')]
        first = parts[0].strip()
        rest  = [p for p in parts[1:] if p]
        if (rest and ' ' not in first
                and not all(p.lower() == first.lower() for p in rest)):
            rec['headword_raw']      = first
            rec['variant_forms_raw'] = ', '.join(rest)
            rec['variant_forms']     = rest

    hw_normalised = re.sub(r'\s+', ' ', rec['headword_raw'] or '').strip()
    hom_m = re.match(r'^(.{2,}?)(\d+)$', hw_normalised)
    if hom_m and not re.search(r'\s', hom_m.group(1).rstrip()):
        rec['headword']      = hom_m.group(1).strip().lower() or None
        rec['homonym_index'] = int(hom_m.group(2))
    else:
        rec['headword']      = hw_normalised.lower() or None
        rec['homonym_index'] = None

    # ── 5. Pronunciations ────────────────────────────────────────────────────
    hdr_end   = _get_header_pron_end(text)
    hdr_prons = PRON_PAT.findall(text[:hdr_end])
    for i, p in enumerate(hdr_prons[:4], 1):
        k = 'pronunciation' if i == 1 else f'pronunciation_{i}'
        rec[k] = _normalize_fullwidth(p.strip())

    # ── 6. Variant forms ─────────────────────────────────────────────────────
    also_m = ALSO_PAT.search(text[:hdr_end + 80])
    if also_m:
        raw = also_m.group(1).strip()
        raw_clean = REGION_PAT.sub('', raw)
        raw_clean = ORPHAN_PAREN.sub('', raw_clean)
        raw_clean = re.sub(r'\s{2,}', ' ', raw_clean).strip().strip(',')
        rec['variant_forms_raw'] = raw_clean or raw
        var_prons  = PRON_SPAN.findall(raw)
        clean_v    = PRON_SPAN.sub('', raw)
        clean_v    = REGION_PAT.sub('', clean_v)
        clean_v    = ORPHAN_PAREN.sub('', clean_v)
        clean_v    = re.sub(r'\s+', ' ', clean_v).strip().strip(',')
        rec['variant_forms'] = (
            [v.strip().strip(')') for v in re.split(r',\s*', clean_v) if v.strip().strip(')')]
            or None
        )
        pron_slots = ['pronunciation_2', 'pronunciation_3']
        slot_idx   = 0
        for vp in var_prons:
            while slot_idx < len(pron_slots) and rec.get(pron_slots[slot_idx]):
                slot_idx += 1
            if slot_idx < len(pron_slots):
                rec[pron_slots[slot_idx]] = _normalize_fullwidth(vp.strip('/'))
                slot_idx += 1

    # ── 7. POS + grammatical label ───────────────────────────────────────────
    after_hdr   = text[hdr_end:]
    skip_m      = ALSO_SKIP.match(after_hdr)
    search_from = after_hdr[skip_m.end():] if skip_m else after_hdr.lstrip()

    pos_m  = None
    qual_m = re.match(r'\s*\([^)]+\)\s+', search_from)
    if qual_m:
        candidate = search_from[qual_m.end():]
        pos_m = POS_PAT.match(candidate.lstrip())
        if pos_m:
            rec['grammatical_labels'] = qual_m.group(0).strip().strip('()')
            search_from = candidate

    if not pos_m:
        pos_m = POS_PAT.match(search_from.lstrip())

    if pos_m:
        rec['part_of_speech'] = pos_m.group(0).rstrip('.,')
        after_pos = search_from.lstrip()[pos_m.end():]
        extra_pos  = []
        remainder  = after_pos.lstrip(' ,')
        while True:
            m2 = POS_PAT_STRICT.match(remainder.lstrip())
            if m2:
                extra_pos.append(m2.group(0).rstrip('.,'))
                remainder = remainder.lstrip()[m2.end():].lstrip(' ,')
            else:
                break
        if extra_pos:
            rec['part_of_speech'] = [rec['part_of_speech']] + extra_pos
            after_pos = remainder
        else:
            gl_m = re.match(r'\s*\(([^)]{2,40})\)', after_pos)
            if gl_m and not rec['grammatical_labels']:
                rec['grammatical_labels'] = gl_m.group(1)
    else:
        num_pos_m = re.search(r'1\.\s+(' + POS_TOKENS_STRICT + r')', after_hdr)
        if num_pos_m:
            rec['part_of_speech'] = num_pos_m.group(1).rstrip('.,')
        else:
            notes.append('POS not found')
            rec['parse_confidence'] = 'medium'

    # ── 8. Body ───────────────────────────────────────────────────────────────
    _pos_was_found = bool(rec.get('part_of_speech'))
    if _pos_was_found:
        body_m = re.search(
            r'(?<!\w)(?:(?<=\s)|^)(?:' + POS_TOKENS_STRICT + r')(?:\s*\([^)]+\))?[,.]?\s*(.*)',
            after_hdr,
            re.DOTALL,
        )
    else:
        body_m = None
    body = (
        body_m.group(1).strip()
        if body_m
        else re.sub(r'^[,.\s]+', '', after_hdr).strip()
    )

    while POS_PAT_STRICT.match(body.lstrip()):
        body = POS_PAT_STRICT.sub('', body, count=1).lstrip(' ,').strip()

    if re.match(r'1\.', body):
        sub_defs = re.split(r'\s+(?=\d+\.)', body)
        defs, etyms, exs, regions = [], [], [], []
        for sd in sub_defs:
            sd_body = NUM_STRIP.sub('', sd)
            d, e, ex = _split_body(sd_body)
            cd, who_ex = _clean_def(d)
            if cd:
                defs.append(cd)
            if who_ex:
                exs.append(who_ex)
            if e:
                etyms.append(e)
            if ex:
                exs.append(ex)
            r = _extract_region_mentions(sd)
            if r:
                regions.extend(r)
        rec['definition']      = defs or None
        rec['etymology']       = etyms or None
        rec['examples']        = '; '.join(exs) if exs else None
        rec['region_mentions'] = _dedup_regions(regions) or None
    else:
        d, e, ex = _split_body(body)
        if ex and not e:
            etym_trail = TRAILING_ETYM_SAFE.search(ex)
            if etym_trail:
                e  = etym_trail.group(0).strip()
                ex = ex[:etym_trail.start()].strip() or None
        cd, who_ex = _clean_def(d)
        rec['definition']      = cd
        if who_ex:
            ex = (ex + '; ' + who_ex) if ex else who_ex
        rec['etymology']       = e or None
        rec['examples']        = ex or None
        rec['region_mentions'] = _dedup_regions(_extract_region_mentions(text))

    # ── 9. Cross-references ──────────────────────────────────────────────────
    xrefs = _extract_see_refs(text)
    rec['cross_references'] = xrefs

    if rec['definition'] and isinstance(rec['definition'], str):
        rec['definition'] = _strip_see(rec['definition']) or rec['definition']
    if rec['definition'] and isinstance(rec['definition'], list):
        rec['definition'] = [_strip_see(d) or d for d in rec['definition']]
    if rec['examples']:
        cleaned_ex = _strip_see(str(rec['examples']))
        new_xrefs  = _extract_see_refs(str(rec['examples']))
        if new_xrefs:
            combined = list(dict.fromkeys((xrefs or []) + new_xrefs))
            rec['cross_references'] = combined or None
        rec['examples'] = cleaned_ex or None

    # H3: ETYMOLOGY_IN_DEFINITION rescue
    if isinstance(rec['definition'], str) and not rec.get('etymology'):
        lt_m = re.search(r'\s+<\s+\w', rec['definition'])
        if lt_m:
            rec['etymology'] = rec['definition'][lt_m.start():].strip()
            rec['definition'] = rec['definition'][:lt_m.start()].strip().rstrip(',') or None

    # H5: MISCLASSIFIED_REDIRECT rescue
    if (rec.get('entry_type') == 'full'
            and not rec.get('etymology') and not rec.get('examples')
            and isinstance(rec.get('definition'), str)):
        defn_stripped = re.sub(r'^[\w,\s\'\u2018\u2019]+,\s*', '', rec['definition']).strip()
        tgt_m = re.match(
            r'^[Ss]ee\s+(-?[A-Z\u00C0-\u024F][A-Z0-9\s\'\-\u00C0-\u024F]+'
            r'|[a-z\u00C0-\u024F]\w+)\.?\s*$',
            defn_stripped
        )
        if tgt_m:
            tgts = [t.strip() for t in re.split(r'[;,]', tgt_m.group(1)) if t.strip()]
            if tgts:
                rec['entry_type']       = 'cross_ref'
                rec['cross_references'] = tgts
                rec['definition']       = None

    # I1: ETYM_IN_EXAMPLES rescue
    if rec.get('examples'):
        ex_str         = str(rec['examples'])
        extracted_etyms = []

        embedded = ETYM_EMBEDDED.findall(ex_str)
        if embedded:
            extracted_etyms.extend(e.strip() for e in embedded)
            ex_str = ETYM_EMBEDDED.sub('', ex_str).strip()

        trail_m = ETYM_TRAILING_BARE.search(ex_str)
        if trail_m:
            extracted_etyms.append(trail_m.group(1).strip())
            ex_str = ex_str[:trail_m.start()].strip()

        if extracted_etyms:
            rec['examples']   = ex_str or None
            existing_etym     = str(rec.get('etymology') or '')
            new_etym_seg      = '; '.join(dict.fromkeys(extracted_etyms))
            if existing_etym:
                if new_etym_seg not in existing_etym:
                    rec['etymology'] = existing_etym + ' ' + new_etym_seg
            else:
                rec['etymology'] = new_etym_seg

    # ── 10. Final confidence ─────────────────────────────────────────────────
    if rec['parse_confidence'] == 'high':
        missing = [f for f in ('headword', 'part_of_speech', 'definition') if not rec.get(f)]
        if missing:
            rec['parse_confidence'] = 'medium'
            notes.append(f'missing: {", ".join(missing)}')

    rec['parse_notes'] = '; '.join(notes) if notes else None

    # ── 11. Coverage ─────────────────────────────────────────────────────────
    cov = check_coverage(rec)
    rec['coverage_pct']       = cov['covered_pct']
    rec['coverage_char_pct']  = cov['coverage_char_pct']
    rec['coverage_uncovered'] = cov['uncovered'] if cov['uncovered'] else None

    return rec


# ---------------------------------------------------------------------------
# Batch convenience
# ---------------------------------------------------------------------------

def parse_all(paragraphs: list) -> list:
    """Parse a list of ``{'paragraph_id': int, 'text': str}`` dicts."""
    return [parse_entry(p['paragraph_id'], p['text']) for p in paragraphs]


def coverage_report(records: list) -> dict:
    """Summarise coverage_pct across all records.

    Returns:
      mean_coverage  float
      below_80       list[dict]
      below_50       list[dict]
    """
    valid = [
        r for r in records
        if r.get('parse_confidence') != 'skip' and r.get('coverage_pct') is not None
    ]
    mean_cov = (
        round(sum(r['coverage_pct'] for r in valid) / len(valid), 1)
        if valid else None
    )

    def _row(r):
        return {
            'para_id': r['para_id'],
            'headword': r.get('headword'),
            'entry_type': r.get('entry_type'),
            'covered_pct': r['coverage_pct'],
        }

    return {
        'mean_coverage': mean_cov,
        'below_80': [_row(r) for r in valid if r['coverage_pct'] < 80],
        'below_50': [_row(r) for r in valid if r['coverage_pct'] < 50],
    }
