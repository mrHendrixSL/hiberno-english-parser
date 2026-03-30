# Data Model

The parser outputs are designed to conform to a simple JSON schema.
This document describes the fields, types and semantics of the three
primary data structures:

* **Rule output** – produced by the rule‑based parser
* **GenAI output** – produced by the LLM parser
* **Merged output** – result of joining the normalised outputs on
  `entry_id`

Formal machine‑readable JSON schemas are provided in the `schemas/`
folder.

## Rule output (`rule_output_schema.json`)

* `entry_id` (integer) – 1‑indexed identifier corresponding to the
  paragraph position in the source document.
* `source_text` (string) – original paragraph text.
* `headword_raw` (string or null) – headword as it appears in the
  source (may include variant forms or punctuation).
* `headword` (string or null) – lower‑cased canonical headword.
* `variant_forms_raw` (string or null) – raw variant forms string.
* `variant_forms` (array of strings) – list of variant headwords.
* `pronunciation`, `pronunciation_2`, `pronunciation_3`,
  `pronunciation_4` (string or null) – up to four pronunciations.
* `part_of_speech` (string or null) – raw POS label.
* `grammatical_labels` (array of strings) – additional labels such as
  “in the phrase”.
* `definition` (string or null) – extracted definition text.
* `etymology` (string or null) – extracted etymology text.
* `cross_references` (array of strings) – target headwords of
  cross‑references.
* `examples` (array of strings) – quoted usage examples.
* `region_mentions` (array of objects) – list of objects with
  `code` and `place` keys indicating geographical mentions.
* `entry_type` (string) – one of `lexical`, `cross_reference`,
  `grammatical_note` or `unparsed`.
* `parse_confidence` (number) – heuristic confidence score in [0, 1].
* `parse_notes` (array of strings) – notes explaining which pattern
  matched or why parsing failed.

## GenAI output (`genai_output_schema.json`)

* `entry_id` (string) – identifier matching the input entry.
* `source_text` (string) – original paragraph text.
* `data` (object) – nested object containing the same semantic fields
  as the rule output but always using arrays for list fields. Keys:
  `headword_raw`, `headword`, `variant_forms_raw`, `variant_forms`,
  `pronunciations`, `part_of_speech`, `definition`, `examples`,
  `etymology`, `cross_references`, `region_mentions`.
* `flags` (object) – validation flags indicating missing headwords,
  missing definitions or malformed examples.
* `needs_review` (boolean) – True if any flag is set.

## Merged output (`merged_output_schema.json`)

The merged output includes all fields from the normalised rule and GenAI
outputs, suffixed with `_rule` or `_genai` to indicate provenance. A
special `_merge` column records whether a row originates from the
rule output only (`left_only`), the GenAI output only (`right_only`) or
both. Additional columns may be added by the evaluation scripts (e.g.
`source_text_exact_match`).

Users should consult the JSON schemas for precise required fields and
types. The schemas are intentionally permissive where the upstream
parsers may omit information (e.g. nullable strings and lists).