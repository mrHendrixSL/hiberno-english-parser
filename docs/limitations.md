# Limitations

## Rule-Based Parser

### Domain Specificity

The parser is tuned to the typographic and structural conventions of
Dolan (2006).  Its regex patterns assume:

- IPA pronunciations are enclosed in forward slashes
- Etymology anchors begin with `< Ir`, `< OE`, etc.
- Informant attributions follow the `(ABBR, County)` pattern
- POS labels from a fixed closed vocabulary

Applying the parser to a different dictionary would require rewriting
the regex layer from scratch.

### Edge Cases

Despite seven rounds of fixes, the parser's parse_confidence logic is
heuristic.  Entries marked `low` or `medium` confidence may have
structural issues the parser did not fully resolve.

The coverage metric is a token-overlap proxy.  An entry with
`coverage_pct = 85` does not necessarily mean 15% of content is lost;
some uncovered tokens may be stopwords not yet in `COVERAGE_STOPWORDS`,
IPA symbols, or citation fragments.

### Numbered Senses

Entries with more than three numbered senses occasionally produce
incomplete definition splits.  The parser stops when the sentence
structure deviates significantly from the expected format.

---

## GenAI Parser

### API Dependency

The pipeline requires an Anthropic API key and a live network connection
by default.  Local LLM endpoint support is available via the
`ANTHROPIC_BASE_URL` environment variable, but the model must match
the expected JSON schema.

### Prompt Sensitivity

Extraction quality is sensitive to the system prompt.  The v2 prompt
adds 5 additional few-shot examples to address known failure modes.
Other edge cases (e.g. highly abbreviated headwords, multi-paragraph
entries) may still produce suboptimal results.

### Hallucination

The hallucination detection in the evaluation framework flags entries
where the LLM output contains tokens not present in the source text.
These flags are a proxy for overgeneration; they cannot distinguish
between genuine errors and legitimate normalisation differences.

### Cost

GenAI extraction is not free.  Run `scripts/run_genai_parser.py --estimate-only`
before a full run to review the approximate cost.

---

## Evaluation Framework

### Normalisation Sensitivity

The exact-agreement metric uses an aggressive normalisation pipeline
(diacritics stripped, lowercase, punctuation removed).  This reduces
false negatives from formatting differences, but may mask genuinely
different content that happens to share the same token set.

### Missing LLM Values

When the LLM produces no output for a field, the evaluation records
that field as null on the LLM side.  The preprocessing step deliberately
does **not** mirror rule-based values for missing LLM fields, so
field-presence statistics accurately reflect what the LLM actually
extracted.

### Dataset Specificity

Coverage and agreement metrics were computed on the 3,507 full entries
in Dolan (2006).  Results should not be assumed to generalise to other
corpora or evaluation conditions.

---

## General

### No Independent Validation

Parse confidence labels and coverage metrics are computed automatically
and have not been validated against human annotations.

### Source Text Quality

The source DOCX file had been semi-cleaned before parsing.  Residual
OCR artefacts or encoding issues in the source may produce unexpected
parse results.
