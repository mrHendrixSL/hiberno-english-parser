# Evaluation Framework

The evaluation pipeline (`src/evaluation/`) compares rule-based and
GenAI outputs entry-by-entry across four dimensions.

---

## Four Evaluation Dimensions

### 1. Field Presence

Whether each field is non-null in rule-based and LLM outputs.

Reported as:
- `rb_pct` — % of entries where RB populates the field
- `llm_pct` — % of entries where LLM populates the field
- `both`, `neither`, `rb_only`, `llm_only` — contingency counts

### 2. Exact Agreement

Normalised string equality between RB and LLM values.

Normalisation pipeline (applied to both before comparison):
1. Flatten to string (lists and dicts become space-joined text)
2. Fullwidth Unicode → ASCII
3. NFD decomposition + remove combining marks (diacritic-insensitive)
4. Lowercase
5. Non-word/non-space chars → space
6. Collapse whitespace

Reported as `exact_agreement_pct` per field.

### 3. Token Similarity

Two complementary similarity metrics computed on token lists:

| Metric | Description |
|---|---|
| **Ordered** | `SequenceMatcher.ratio()` on token lists (order-sensitive) |
| **Unordered** | F1 overlap between token sets (order-insensitive) |

Both range from 0.0 (no overlap) to 1.0 (identical).

### 4. Source Coverage

Pre-computed on each record by the parser/extractor:
- `coverage_pct` — % of source tokens found in extracted fields
- `coverage_char_pct` — % of source characters in extracted content

---

## Per-Stratum Breakdown

Entries are tagged with stratum membership at evaluation time.
No pre-sampling is needed.

| Stratum | Criterion |
|---|---|
| `high_confidence` | `parse_confidence == "high"` |
| `medium_confidence` | `parse_confidence == "medium"` |
| `low_confidence` | `parse_confidence == "low"` |
| `numbered_senses` | `definition` is a list |
| `who_adds` | `"who adds"` in `full_text` |
| `multi_pronunciation` | `pronunciation_2` is not null |
| `variant_forms` | `variant_forms` is not null |
| `with_etymology` | `etymology` is not null |
| `multi_region` | 2+ `region_mentions` |
| `long_definition` | `definition` > 120 characters |

---

## Misclassification Flags

Additional per-entry flags detecting common LLM extraction errors:

| Flag | Meaning |
|---|---|
| `etym_in_definition` | LLM definition contains a `<` etymology marker |
| `examples_in_definition` | LLM definition contains quotes but RB has examples |
| `chained_etym_collapsed` | RB has `< A < B`, LLM has only one `<` |
| `examples_dropped` | RB has examples, LLM does not |
| `numbered_senses_not_split` | RB definition is a list, LLM returns a string |
| `cross_ref_missed` | RB has cross-references, LLM does not |
| `any` | Any of the above flags set |

---

## Output Files

### comparison.json

Top-level structure:
```json
{
  "meta": { "n_total": 3899, "n_rb_full": 3507, ... },
  "classification_disagreements": [...],
  "aggregate": {
    "n": 3507,
    "exact_agreement_pct": { "headword": 98.1, ... },
    "token_similarity": { ... },
    "field_presence": { ... },
    "coverage": { ... },
    "misclassification_counts": { ... },
    "stratum_agreement": { "stratum_high_confidence": { ... }, ... }
  },
  "entries": [
    {
      "para_id": 1,
      "full_text": "...",
      "rb": { "headword": "...", ... },
      "llm": { "headword": "...", ... },
      "comparison": {
        "agree_pct": 85.7,
        "exact_agreement": { ... },
        "token_similarity": { ... },
        "rb_coverage_pct": 92.0,
        "llm_coverage_pct": 88.5,
        "misclassification_flags": { ... },
        "strata": { ... }
      }
    }
  ]
}
```

### comparison.xlsx

Eight sheets:
1. `entries` — one row per entry, all fields flattened
2. `exact_agreement` — sorted by agreement %
3. `token_similarity` — ordered and unordered means
4. `field_presence` — presence counts and %s
5. `coverage` — coverage summary statistics
6. `misclassification` — flag counts
7. `stratum_agreement` — exact agreement % by stratum × field
8. `disagreements` — entries where RB=full but LLM≠full

---

## Running the Pipeline

```bash
# With defaults from configs/evaluation_config.yaml
python scripts/run_evaluation.py

# With explicit paths
python scripts/run_evaluation.py \
  --rb data/rule_based_output.json \
  --llm outputs/genai/llm_output_v2.json

# Skip Excel export
python scripts/run_evaluation.py --no-excel
```
