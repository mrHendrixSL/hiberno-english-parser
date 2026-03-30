# Evaluation Framework

The evaluation framework provides systematic tools for comparing the
outputs of the rule‑based and GenAI parsers. It focuses on
transparency, reproducibility and actionable diagnostics.

## Pipeline

1. **Load raw outputs** – both parsers produce JSONL files with
   heterogeneous schemas. These are loaded into DataFrames using
   `read_jsonl`.
2. **Flatten GenAI output** – nested `data` and `flags` objects are
   flattened into top‑level columns using `pandas.json_normalize`.
3. **Normalise** – rule and GenAI outputs are cleaned and coerced
   into a shared schema (see `CORE_FIELDS` in `src/evaluation/normalize.py`).
4. **Apply maps** – optional POS and region normalisation maps can be
   applied to harmonise labels across parsers.
5. **Merge** – the two DataFrames are merged on the integer `entry_id`.
   Rows are marked as `both`, `left_only` (rule only) or `right_only`
   (GenAI only).
6. **Alignment check** – a simple exact match of the source texts is
   performed to flag potential misalignments between the two outputs.
7. **Presence/absence summary** – for each field the framework counts
   how often it is present in both outputs, only in the rule output,
   only in the GenAI output or missing from both.
8. **Exact match summary** – for each field it computes the fraction
   of entries where the cleaned values match exactly.
9. **Containment diagnostics** – optional metrics (not run by default
   in the scripts) measure how well extracted content is grounded in the
   source text using consumptive token matching.

## Interpretation

The evaluation does not declare one parser “better” than the other.
Rather, it surfaces differences and guides further investigation. For
instance:

* A high `rule_only` count for a field suggests the GenAI parser is
  omitting information that the rule‑based parser captures.
* A high `genai_only` count suggests the rule‑based parser is missing
  legitimate content extracted by the LLM.
* A low exact match rate may point to different normalisation
  strategies or hallucinations.

Users are encouraged to build additional metrics or visualisations on
top of the merged dataset. See `src/evaluation/metrics.py` for token
level containment functions.