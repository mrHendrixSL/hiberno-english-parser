# Hiberno-English Parser

A modular, reproducible codebase for parsing and evaluating structured
field extraction from *A Dictionary of Hiberno-English* (Dolan, 2006).

Two complementary extraction pipelines are provided, along with a
side-by-side evaluation framework:

| Pipeline | Approach |
|---|---|
| **Rule-based** | Regular expressions + heuristics (v7, ~30 compiled patterns) |
| **GenAI** | LLM-assisted extraction via the Anthropic API |

---

## Repository Structure

```
hiberno-english-parser/
├── configs/                        # YAML configuration files
│   ├── rule_parser_config.yaml
│   ├── genai_config.yaml
│   └── evaluation_config.yaml
├── prompts/                        # System prompt text files for GenAI
│   ├── system_prompt.txt           # 6 few-shot examples
│   └── system_prompt_v2.txt        # 11 few-shot examples (improved)
├── src/
│   ├── shared/                     # Shared utilities
│   │   ├── schema.py               # Centralised field definitions
│   │   ├── normalisation.py        # Unicode normalisation + metric helpers
│   │   ├── io_utils.py             # JSON I/O helpers
│   │   ├── config_loader.py        # YAML config loading
│   │   └── audit.py                # Version management + diff utilities
│   ├── rule_based/
│   │   └── parser.py               # Core rule-based parser (v7)
│   ├── genai/
│   │   ├── extractor.py            # LLM extraction runner
│   │   └── rerun.py                # Re-extraction for flagged entries
│   └── evaluation/
│       ├── metrics.py              # Per-entry + aggregate metrics (dict + DataFrame)
│       ├── coverage.py             # Token/char coverage computation
│       ├── preprocessing.py        # Merge rule-based + LLM outputs
│       ├── aggregation.py          # Aggregate statistics + entry record builder
│       ├── export.py               # Multi-sheet Excel export
│       └── pipeline.py             # Full evaluation orchestrator
├── scripts/                        # Thin CLI entry points
│   ├── run_rule_parser.py
│   ├── run_genai_parser.py
│   ├── run_genai_rerun.py
│   └── run_evaluation.py
├── tests/                          # Pytest test suite
├── notebooks/                      # Demo notebooks
├── docs/                           # Documentation
├── examples/                       # Sample input/output examples
├── data/                           # Input data (not committed, see below)
└── outputs/                        # Generated outputs (not committed)
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/[your-org]/hiberno-english-parser.git
cd hiberno-english-parser

# Install dependencies
pip install -r requirements.txt

# Or install as a package (editable mode)
pip install -e ".[dev]"
```

---

## Configuration

All paths and settings are managed through YAML files in `configs/`.
Paths are relative to the repository root.

**Optional:** Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=...
```

---

## How to Run

### 1. Rule-based parser

Parse raw dictionary paragraphs into structured JSON records:

```bash
python scripts/run_rule_parser.py
# or override paths:
python scripts/run_rule_parser.py --input data/paragraphs.json --output data/rule_based_output.json
```

**Input:** `data/paragraphs.json` — list of `{"paragraph_id": int, "text": str}` objects.  
**Output:** `data/rule_based_output.json` — list of structured entry records.

---

### 2. GenAI extraction

Extract structured fields using the Anthropic API:

```bash
# Estimate cost first (no API calls made):
python scripts/run_genai_parser.py --estimate-only

# Run extraction (resumes from checkpoint if output already exists):
python scripts/run_genai_parser.py
```

**Requires:** `ANTHROPIC_API_KEY` in environment or `.env`.  
**Input:** `data/rule_based_output.json`  
**Output:** `outputs/genai/llm_output.json`

---

### 3. GenAI re-extraction (optional)

Re-extract flagged low-quality entries with the improved prompt:

```bash
python scripts/run_genai_rerun.py
```

Entries are flagged by coverage, confidence, or missing fields.
Merged output: `outputs/genai/llm_output_v2.json`

---

### 4. Evaluation

Compare rule-based and GenAI outputs across four dimensions:

```bash
python scripts/run_evaluation.py
# or override inputs:
python scripts/run_evaluation.py --rb data/rule_based_output.json --llm outputs/genai/llm_output_v2.json
```

**Output:**
- `outputs/evaluation/comparison.json` — full per-entry comparison + aggregate stats
- `outputs/evaluation/comparison.xlsx` — 8-sheet Excel workbook

---

## Data Model

Each parsed entry record contains the following fields:

| Field | Type | Description |
|---|---|---|
| `para_id` | int | Paragraph identifier (unique) |
| `full_text` | str | Original source text |
| `entry_type` | str | `full`, `cross_ref`, or `header` |
| `headword_raw` | str | Headword as it appears in source |
| `headword` | str | Normalised lowercase headword |
| `homonym_index` | int \| null | Trailing digit on headwords (e.g. `bac1` → 1) |
| `variant_forms_raw` | str \| null | Raw variant string from source |
| `variant_forms` | list[str] \| null | Cleaned list of alternate spellings |
| `pronunciation` | str \| null | IPA (slashes stripped) |
| `pronunciation_2/3` | str \| null | Additional pronunciation variants |
| `part_of_speech` | str \| list[str] \| null | POS label(s) |
| `grammatical_labels` | str \| null | Register/usage labels (e.g. `colloq.`) |
| `definition` | str \| list[str] \| null | Single sense or numbered senses list |
| `etymology` | str \| list[str] \| null | Etymology marker(s) |
| `examples` | str \| null | Usage examples joined with `; ` |
| `cross_references` | list[str] \| null | `See X.` targets |
| `region_mentions` | list[{informant, county}] \| null | Informant attributions |
| `parse_confidence` | str | `high`, `medium`, `low`, or `skip` |
| `parse_notes` | str \| null | Diagnostic notes |
| `coverage_pct` | float \| null | % of source tokens accounted for |
| `coverage_char_pct` | float \| null | % of source characters in extracted fields |

See [docs/data_model.md](docs/data_model.md) for full details.

---

## Evaluation Metrics

The evaluation pipeline computes four dimensions:

| Dimension | Description |
|---|---|
| **Field presence** | Which fields are populated (non-null) per approach |
| **Exact agreement** | Normalised string equality between RB and LLM values |
| **Token similarity** | Ordered (SequenceMatcher) and unordered (F1) token overlap |
| **Source coverage** | Token and character coverage against source text |

Results are reported per-entry, per-stratum, and in aggregate.
See [docs/evaluation_framework.md](docs/evaluation_framework.md).

---

## Local LLM Endpoint Support

The GenAI pipeline targets the Anthropic API by default.
To use a local endpoint, set `ANTHROPIC_BASE_URL` in `.env`:

```
ANTHROPIC_BASE_URL=http://localhost:8080
```

The `anthropic` client will route all API calls through that URL.
Ensure your local model responds with the same JSON structure as Claude.

---

## Limitations

See [docs/limitations.md](docs/limitations.md) for a full discussion.
Key limitations include:

- The rule-based parser is tuned to Dolan (2006) entry conventions;
  generalisability to other dictionaries is limited.
- GenAI extraction depends on the Anthropic API; offline use requires
  configuring a local LLM proxy.
- Parse confidence ratings are heuristic and not independently validated.
- Coverage metrics are token-overlap proxies and do not capture semantic completeness.

---

## Citation

If you use this software in your research, please cite it using the
metadata in [CITATION.cff](CITATION.cff).

The underlying dictionary is:

> Dolan, T. P. (2006). *A Dictionary of Hiberno-English: The Irish Use
> of English* (2nd ed.). Gill & Macmillan.

---

## License

MIT — see [LICENSE](LICENSE).
