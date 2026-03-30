# Limitations

Despite significant refactoring efforts, the Hiberno‑English parser
remains a research prototype. Users should be aware of the following
limitations:

* **Domain specificity** – the rule‑based heuristics were derived from
  the formatting conventions of *A Dictionary of Hiberno‑English* and
  may not generalise to other dictionaries or editions without
  modification.
* **Parser brittleness** – unexpected punctuation, layout quirks or
  novel expressions can cause the rule‑based parser to misclassify
  entries. The confidence scores and audit flags should be used to
  identify suspect records.
* **LLM variability** – the GenAI parser depends on a large language
  model. Different models or parameters may produce divergent outputs.
  There is currently no retry or repair logic implemented in the
  scripts.
* **Incomplete evaluation** – the evaluation metrics focus on
  exact matches and presence/absence. They do not assess semantic
  equivalence or capture partial overlaps in extracted content.
* **Resource incompleteness** – the normalisation maps (`pos_map.json`
  and `region_normalization_map.json`) are derived from the training
  data provided and may not cover every possible abbreviation or
  location. They can be extended by editing the JSON files in
  `resources/`.

Future work could include more sophisticated alignment algorithms,
confidence calibration for the LLM, richer evaluation metrics and
interactive annotation tools.