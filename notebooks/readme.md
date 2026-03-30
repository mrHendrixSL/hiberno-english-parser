Notebooks (Exploratory & Legacy Workflows)

This directory contains the original Jupyter notebooks used during the development and prototyping phase of the Hiberno-English parser project.

⚠️ Important Notice

These notebooks are not part of the reproducible pipeline.

They are retained for:

transparency of research development
inspection of intermediate approaches
documentation of exploratory experiments

The canonical, reproducible implementation is located in:

src/ → modular pipeline logic
scripts/ → runnable workflows
configs/ → configuration files
📂 Notebook Overview
hiberno_lexical_parser_V_12.ipynb
Original rule-based parsing workflow
Contains regex heuristics and early schema assumptions
Includes experimental parsing strategies and edge-case handling
gpt4all_V3.ipynb
Initial GenAI-based structured extraction pipeline
Uses GPT4All / LLM prompting for parsing dictionary entries
Contains prompt iterations and output validation experiments
hiberno_parser_evaluation_clean_workflow.ipynb
Prototype evaluation workflow
Includes alignment logic, metric exploration, and hallucination proxies
Precedes the modular evaluation pipeline in src/evaluation/
🧪 Characteristics of These Notebooks

These notebooks may include:

hard-coded file paths (since removed in the main pipeline)
experimental or unused code cells
intermediate outputs and debug prints
manual execution steps
partial or evolving schema definitions

They reflect the research process, not the final system.

🚀 Recommended Usage

Use these notebooks only for:

understanding design decisions
tracing the evolution of parsing strategies
reproducing exploratory experiments (with caution)

Do not use them as the primary interface for running the system.

✅ For Reproducible Execution

To run the project in a clean and reproducible way, use:

python scripts/run_rule_parser.py --config configs/rule_parser_config.yaml
python scripts/run_genai_parser.py --config configs/genai_config.yaml
python scripts/run_evaluation.py --config configs/evaluation_config.yaml