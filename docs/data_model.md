# Data Model

## Entry Record Schema

Each record produced by either the rule-based or GenAI parser contains
the following fields.

### Identifier Fields

| Field | Type | Description |
|---|---|---|
| `para_id` | `int` | Unique paragraph identifier from source |
| `full_text` | `str` | Original source text (verbatim) |

### Classification Fields

| Field | Type | Values |
|---|---|---|
| `entry_type` | `str` | `"full"`, `"cross_ref"`, `"header"` |
| `parse_confidence` | `str` | `"high"`, `"medium"`, `"low"`, `"skip"` |

### Headword Fields

| Field | Type | Description |
|---|---|---|
| `headword_raw` | `str \| null` | Headword as it appears in source (original capitalisation) |
| `headword` | `str \| null` | Normalised lowercase form |
| `homonym_index` | `int \| null` | Trailing digit from headword (e.g. `bac1` → 1) |
| `variant_forms_raw` | `str \| null` | Raw variant string from `also X` block |
| `variant_forms` | `list[str] \| null` | Cleaned list of alternate spellings |

### Pronunciation Fields

| Field | Type | Description |
|---|---|---|
| `pronunciation` | `str \| null` | Primary IPA (forward slashes stripped) |
| `pronunciation_2` | `str \| null` | Secondary pronunciation |
| `pronunciation_3` | `str \| null` | Tertiary pronunciation |

### Grammatical Fields

| Field | Type | Description |
|---|---|---|
| `part_of_speech` | `str \| list[str] \| null` | POS label; list when multiple (e.g. `["n", "v"]`) |
| `grammatical_labels` | `str \| null` | Register/usage labels (e.g. `"colloq."`, `"pejor."`) |

### Content Fields

| Field | Type | Description |
|---|---|---|
| `definition` | `str \| list[str] \| null` | Single sense or numbered-sense list |
| `etymology` | `str \| list[str] \| null` | Etymology marker(s) starting with `<` |
| `examples` | `str \| null` | Usage examples joined with `"; "` |
| `cross_references` | `list[str] \| null` | Targets from `See X.` patterns |
| `region_mentions` | `list[{informant: str, county: str}] \| null` | Informant attributions |

### Coverage / Diagnostic Fields

| Field | Type | Description |
|---|---|---|
| `coverage_pct` | `float \| null` | % of source tokens found in extracted fields |
| `coverage_char_pct` | `float \| null` | % of source chars in extracted content |
| `coverage_uncovered` | `list[str] \| null` | Tokens not found in any field |
| `parse_notes` | `str \| null` | Diagnostic notes from parser |

### GenAI-Only Fields

These fields appear only in LLM extraction outputs:

| Field | Type | Description |
|---|---|---|
| `changed` | `bool` | Marked `True` after re-extraction |
| `changed_fields` | `list[str]` | Fields changed from v1 to v2 extraction |
| `rerun_v2` | `bool` | Present and `True` if entry was re-run |
| `v1_reasons` | `list[str]` | Flag reasons that triggered re-extraction |

---

## Field Type Conventions

### `part_of_speech`

A single string for single-POS entries:
```json
"part_of_speech": "n"
```

A list for dual-POS entries:
```json
"part_of_speech": ["n", "v"]
```

Known POS values include: `n`, `v`, `adj`, `adv`, `n.phr`, `v.phr`,
`adv.phr`, `adj.phr`, `voc`, `interj`, `int`, `conj`, `pron`, `excl`,
`prep`, `num`, `pl`, `pers`, `part`, `place-name`, `suffix`, `prefix`,
`acronym`, `verbal n`, `pronominal phr`, `possessive adj`,
`personal pron`, `reflexive pron`, `indefinite article`.

### `definition`

Single sense:
```json
"definition": "irregular red lines on children's shins"
```

Numbered senses (list):
```json
"definition": ["sense one", "sense two", "sense three"]
```

### `region_mentions`

```json
"region_mentions": [
  {"informant": "SOM", "county": "Kerry"},
  {"informant": "BC",  "county": "Meath"}
]
```

---

## Centralised Field Lists

Field-name constants are defined in `src/shared/schema.py`:

- `EXTRACTED_FIELDS` — fields the LLM extracts
- `PIPELINE_INJECTED` — fields added by the pipeline
- `CONTENT_FIELDS` — fields compared in evaluation
- `KEEP_FIELDS` — fields retained in comparison DataFrame
- `COVERAGE_FIELDS_RB` — fields used for rule-based coverage
- `COVERAGE_FIELDS_EVAL` — fields used for evaluation coverage
- `STRATUM_COLS`, `MISCLASS_COLS` — evaluation column names
