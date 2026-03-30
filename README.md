# Hiberno‑English Parser

This repository contains a clean, modular and reproducible codebase for
parsing entries from **A Dictionary of Hiberno‑English**. Two
alternative pipelines are provided:

* **Rule‑based parser** – applies regular expressions and heuristics to
  extract structured fields from raw dictionary paragraphs.
* **GenAI parser** – uses a large language model (LLM) to perform
  structured extraction from raw text with guidance from externalised
  prompts.

An evaluation framework enables side‑by‑side comparison of the two
approaches, including field‑level presence/absence statistics and exact
match rates.

## Project structure

```
hiberno-english-parser/
├── README.md              # This file
├── LICENSE                # Project licence (MIT)
├── CITATION.cff           # How to cite this repository
├── requirements.txt       # Python dependencies
├── .env.example           # Template for environment variables
├── configs/               # YAML configuration files
│   ├── rule_parser_config.yaml
│   ├── genai_config.yaml
│   └── evaluation_config.yaml
├── resources/             # Normalisation maps and resource files
│   ├── pos_map.json
│   ├── usage_labels.json
│   ├── region_normalization_map.json
│   └── drop_values.json
├── prompts/               # Externalised LLM prompts
│   ├── system_prompt.txt
│   ├── parser_prompt.txt
│   └── repair_prompt.txt
├── src/                   # Application source code
│   ├── rule_based/        # Rule‑based parsing logic
│   ├── genai/             # GenAI parsing logic
│   ├── evaluation/        # Evaluation and comparison logic
│   └── shared/            # Utilities and config helpers
├── scripts/               # Command‑line entry points
│   ├── run_rule_parser.py
│   ├── run_genai_parser.py
│   └── run_evaluation.py
├── examples/              # Small sample dataset and outputs
├── notebooks/             # Lightweight notebooks for demonstrations
├── tests/                 # Unit tests
└── docs/                  # Additional documentation
```

## Getting started

### Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/your‑org/hiberno‑english‑parser.git
cd hiberno‑english‑parser
pip install -r requirements.txt
```

The project requires Python ≥ 3.9. Some components (e.g. LLM parsing)
also depend on external services. You should create a `.env` file based
on `.env.example` and supply any required API keys (for example
`OPENAI_API_KEY`).

### Rule‑based parser

The rule‑based parser processes a DOCX file containing dictionary
entries and outputs a JSON Lines file of structured records. Edit
`configs/rule_parser_config.yaml` to point to your DOCX and desired
output locations. Then run:

```bash
python scripts/run_rule_parser.py --config configs/rule_parser_config.yaml
```

The script writes two optional outputs:

* `rule_parser_output.jsonl` – one JSON record per entry
* `rule_parser_audit.csv` – audit of paragraphs with simple flags

### GenAI parser

The GenAI parser uses a large language model to extract fields from
paragraphs. Prepare an input file containing a list of objects with
`entry_id` and `entry_text` fields (see `examples/sample_entries.json` for
guidance). Configure the model endpoint and other settings in
`configs/genai_config.yaml` then run:

```bash
python scripts/run_genai_parser.py --config configs/genai_config.yaml
```

The script appends results to `genai_parser_output.jsonl` and logs
errors to `genai_parser_errors.jsonl`. Prompts are externalised in the
`prompts/` folder and can be modified without touching code.

### Evaluation

To compare the rule‑based and GenAI outputs, adjust
`configs/evaluation_config.yaml` to point to the output files produced
by the parsers. Then run:

```bash
python scripts/run_evaluation.py --config configs/evaluation_config.yaml
```

The evaluation script normalises both outputs, applies optional
normalisation maps (POS and region), merges them on the numeric
`entry_id` and produces:

* `merged_output.jsonl` – combined dataset with suffixes `_rule` and
  `_genai`
* `presence_summary.csv` – per‑field presence/absence statistics
* `exact_match_summary.csv` – per‑field exact match rates

An optional Excel file (`summaries.xlsx`) is also created if the
environment supports writing Excel files.

## Documentation

Further details about the methodology, evaluation framework, data
model and limitations are provided in the `docs/` folder:

* **`methodology.md`** – description of parsing heuristics and GenAI
  prompts
* **`evaluation_framework.md`** – explanation of the comparison metrics
  and alignment logic
* **`data_model.md`** – specification of the output schema and JSON
  schemas
* **`limitations.md`** – known limitations and assumptions

## Sample data and examples

The `examples/` directory contains a small sample dataset of 10
dictionary entries along with example outputs from both parsers and the
merged result. These examples can be used to quickly test the pipelines
or as templates for building your own datasets.

## Citing this work

If you use this repository or the associated dataset in your research,
please cite it as described in `CITATION.cff`.

## License

This project is licensed under the terms of the MIT License. See
`LICENSE` for details.