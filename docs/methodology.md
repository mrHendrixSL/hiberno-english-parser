# Methodology

This document outlines the design principles and parsing heuristics used
by the **Hiberno‑English Parser**. The project separates the parsing
logic into two independent pipelines: a **rule‑based parser** and a
**GenAI parser**. Both pipelines aim to produce a consistent schema for
lexical entries from *A Dictionary of Hiberno‑English*.

## Rule‑based parser

The rule‑based parser uses regular expressions and deterministic
heuristics to identify structural elements in each dictionary
paragraph. Key aspects include:

* **Normalization** – raw paragraphs are cleaned by collapsing
  whitespace, removing extraneous spacing around punctuation and
  resolving malformed slash notation.
* **Pattern matching** – entry types such as cross‑references,
  phrase/expression labels and grammatical notes are detected via
  carefully ordered regular expressions. Each pattern extracts
  headwords, pronunciations, variant forms, part‑of‑speech labels,
  definitions, etymologies, cross references and region mentions.
* **Confidence scores** – the parser assigns a nominal confidence to
  each record based on how well the pattern matched. Fallback cases are
  marked as ``unparsed`` with low confidence.

The implementation lives in `src/rule_based/parser.py` and is
entirely independent of I/O. Paragraph extraction from DOCX files is
handled separately by `src/rule_based/docx_reader.py`.

## GenAI parser

The GenAI parser delegates extraction to a large language model (LLM).
Prompts are externalised in the `prompts/` directory:

* **`system_prompt.txt`** – establishes the assistant persona and
  instructs it to return strict JSON.
* **`parser_prompt.txt`** – specifies the keys to extract and how to
  structure the JSON output.
* **`repair_prompt.txt`** – used to recover from malformed outputs (not
  implemented in the current scripts but provided as a template).

The LLM output is parsed and validated in `src/genai/parser.py`. Scalar
fields are coerced to strings, lists are coerced to arrays and
validation flags are raised for missing headwords, missing definitions
and malformed examples.

## Normalisation

Both parsers can produce messy outputs. The evaluation framework
includes a normalisation layer (`src/evaluation/normalize.py`) which
performs:

* Unicode normalisation and whitespace cleanup
* Conversion of scalars and lists to canonical types
* Lowercasing and casefolding of part‑of‑speech labels
* De‑duplication of lists while preserving order

Optional maps (`resources/pos_map.json` and
`resources/region_normalization_map.json`) can be used to harmonise
terminology across sources.

## Known limitations

No parser is perfect. The rule‑based parser is brittle when faced with
unexpected formatting or novel constructions. The GenAI parser depends
on the quality of the underlying model and may hallucinate content or
misinterpret the prompt. Users are encouraged to inspect the audit
flags and validation flags and to contribute improvements via pull
requests.