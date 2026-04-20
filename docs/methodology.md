# Methodology

## Source Material

*A Dictionary of Hiberno-English* (Dolan, 2006) contains approximately
3,900 paragraphs extracted from a Word document (`.docx`).  Each
paragraph corresponds to one dictionary entry or section header.

Paragraphs were extracted into a `paragraphs.json` file:

```json
[
  {"paragraph_id": 1, "text": "ABCs /eːbiːsiːz/ n. (colloq.), ..."},
  ...
]
```

---

## Rule-Based Parser

The rule-based parser (`src/rule_based/parser.py`) is a carefully
engineered sequence of regular-expression extraction steps.  It has
gone through seven rounds of fixes (v1–v7), each addressing systematic
edge cases identified during row-level audits.

### Entry Types

| Type | Criterion |
|---|---|
| `header` | Single uppercase letter (section divider: "A", "B", …) |
| `cross_ref` | No pronunciation + redirect pattern (`X, see Y.`) |
| `full` | All other entries |

### Extraction Steps

1. **Section header detection** — single uppercase letter → `header`
2. **Redirect detection** — `REDIRECT_PAT` + no `/pron/` → `cross_ref`
3. **No-pronunciation path** — entries without `/pron/` are processed
   with best-effort heuristics; confidence is `low` or `medium`
4. **Headword** — `HW_PAT` captures text before first `/pron/`
5. **Pronunciations** — up to three IPA spans between `/slashes/`
6. **Variant forms** — `also X` block in the header zone
7. **Part of speech** — `POS_PAT` matches 30+ token types in order
8. **Body** — text after POS boundary is passed to `_split_body()`
9. **Cross-references** — `See X.` targets extracted and See-stripped
10. **Post-hoc rescues** — etymology-in-definition, etymology-in-examples,
    misclassified redirects
11. **Coverage** — token and character coverage computed on the final record

### `_split_body()` Logic

The body (text after POS token) is split into definition, etymology,
and examples using three anchors tried in priority order:

1. `ETYM_HARD_STOP` — complete `< Ir.` followed immediately by a quote
2. `ETYM_START` + `_first_example_boundary()` — standard case
3. Example boundary only (no etymology)

### Coverage Calculation

Token coverage measures what fraction of source-text tokens appear in
at least one extracted field.  Structural stopwords (function words,
etymological language codes, POS labels) are excluded from both
numerator and denominator.

Character coverage measures total characters in extracted content
as a fraction of source text length.  It catches truncation that
token coverage misses (e.g. long examples dropped entirely).

---

## GenAI Parser

The GenAI parser (`src/genai/extractor.py`) calls the Anthropic Claude
API in batches of 5 entries per request.  The system prompt is stored
in `prompts/system_prompt_v2.txt` and contains:

- A description of the entry format conventions
- The 17-field JSON schema
- 11 detailed few-shot examples covering all major edge cases

### Batch Processing

- Entries are sent in batches; the model returns a JSON array
- If the batch response cannot be parsed, each entry is retried individually
- Exponential backoff (up to 64 seconds) handles rate limits
- Checkpoints are written every 50 entries for resumability

### Re-Extraction Workflow

After an initial pass, entries are flagged for re-extraction if they show:

- Coverage below 70%
- Medium parse confidence
- Examples dropped relative to rule-based output
- Chained etymology collapsed to a single source
- Numbered senses not split into a list
- Cross-references missed

Flagged entries are re-run with the improved prompt (`system_prompt_v2.txt`)
and the improved records replace originals in the merged output.
