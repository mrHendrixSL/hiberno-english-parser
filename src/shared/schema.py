"""
schema.py
=========
Centralised field-name definitions shared across rule-based, GenAI, and
evaluation modules.  Import from here rather than re-defining locally.
"""

# Fields the LLM is asked to extract (order matches prompt schema).
EXTRACTED_FIELDS: list[str] = [
    "headword",
    "headword_raw",
    "variant_forms",
    "pronunciation",
    "pronunciation_2",
    "pronunciation_3",
    "part_of_speech",
    "grammatical_labels",
    "definition",
    "etymology",
    "cross_references",
    "examples",
    "region_mentions",
    "entry_type",
    "parse_confidence",
]

# Fields injected by the pipeline (not extracted from source text).
PIPELINE_INJECTED: list[str] = [
    "para_id",
    "full_text",
    "homonym_index",
    "variant_forms_raw",
    "parse_notes",
    "coverage_pct",
    "coverage_char_pct",
    "coverage_uncovered",
    "changed",
    "changed_fields",
]

# All fields in a fully populated record.
ALL_FIELDS: list[str] = PIPELINE_INJECTED + EXTRACTED_FIELDS

# Fields used when computing token-level coverage (rule-based context).
# Uses variant_forms_raw because that is what the rule-based parser produces.
COVERAGE_FIELDS_RB: list[str] = [
    "headword_raw",
    "pronunciation",
    "pronunciation_2",
    "pronunciation_3",
    "part_of_speech",
    "grammatical_labels",
    "variant_forms_raw",
    "definition",
    "etymology",
    "examples",
    "cross_references",
    "region_mentions",
]

# Fields used when computing coverage in the evaluation pipeline
# (both pipelines normalised to use variant_forms as the structured list).
COVERAGE_FIELDS_EVAL: list[str] = [
    "headword_raw",
    "variant_forms",
    "pronunciation",
    "pronunciation_2",
    "pronunciation_3",
    "part_of_speech",
    "grammatical_labels",
    "definition",
    "etymology",
    "cross_references",
    "examples",
    "region_mentions",
]

# Fields compared in the evaluation (content fields only).
CONTENT_FIELDS: list[str] = [
    "headword",
    "headword_raw",
    "homonym_index",
    "variant_forms",
    "pronunciation",
    "pronunciation_2",
    "pronunciation_3",
    "part_of_speech",
    "grammatical_labels",
    "definition",
    "etymology",
    "cross_references",
    "examples",
    "region_mentions",
]

# Fields preserved when merging rule-based and LLM outputs for comparison.
KEEP_FIELDS: list[str] = [
    "entry_type",
    "headword_raw",
    "headword",
    "homonym_index",
    "variant_forms_raw",
    "variant_forms",
    "pronunciation",
    "pronunciation_2",
    "pronunciation_3",
    "part_of_speech",
    "grammatical_labels",
    "definition",
    "etymology",
    "cross_references",
    "examples",
    "region_mentions",
]

# Stratum column names added during evaluation.
STRATUM_COLS: list[str] = [
    "stratum_high_confidence",
    "stratum_medium_confidence",
    "stratum_low_confidence",
    "stratum_numbered_senses",
    "stratum_who_adds",
    "stratum_multi_pronunciation",
    "stratum_variant_forms",
    "stratum_with_etymology",
    "stratum_multi_region",
    "stratum_long_definition",
]

# Misclassification flag column names added during evaluation.
MISCLASS_COLS: list[str] = [
    "misclass_etym_in_definition",
    "misclass_examples_in_definition",
    "misclass_chained_etym_collapsed",
    "misclass_examples_dropped",
    "misclass_numbered_senses_not_split",
    "misclass_cross_ref_missed",
    "misclass_any",
]
