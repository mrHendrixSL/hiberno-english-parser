"""GenAI parser for the Hiberno‑English dictionary.

This module wraps an LLM API (such as OpenAI) to extract structured
fields from raw dictionary entries. Prompts are externalised in the
``prompts/`` directory and loaded at runtime. The parser is designed
to be deterministic given fixed model settings and uses simple
validation and normalisation steps to produce a consistent output
schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple, Dict, Any

from openai import OpenAI

from ..shared.utils import clean_text, ensure_list


def load_prompt(path: str | Path) -> str:
    """Read a prompt template from disk."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return f.read().rstrip()


def build_user_prompt(template: str, entry_text: str) -> str:
    """Render the parser prompt template by inserting the entry text."""
    return template.replace("{{ entry_text }}", entry_text.strip())


def safe_parse_json(text: str) -> Tuple[Dict[str, Any] | None, str]:
    """Attempt to parse a JSON object from a string.

    Returns a tuple of (parsed_object, error_message). If parsing
    succeeds the error message is an empty string; otherwise the parsed
    object is None and the error message describes the failure. The
    function attempts to locate the first and last curly braces and
    reparse in case of leading or trailing text.
    """
    try:
        return json.loads(text), ""
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1]), ""
            except Exception as e:
                return None, str(e)
        return None, "no json found"


def normalize_parsed_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and coerce the fields returned by the model.

    Scalar fields are trimmed strings (missing values become empty
    strings). List fields are coerced to lists and cleaned of nullish
    values. If a field is absent in ``obj`` it is filled with an empty
    value according to its expected type.
    """
    expected_list_fields = [
        "pronunciations",
        "examples",
        "cross_references",
        "region_mentions",
    ]
    expected_scalar_fields = [
        "headword_raw",
        "headword",
        "part_of_speech",
        "definition",
        "etymology",
    ]
    cleaned: Dict[str, Any] = {}
    # scalars
    for key in expected_scalar_fields:
        value = obj.get(key, "")
        if value is None:
            value = ""
        elif not isinstance(value, str):
            value = str(value)
        cleaned[key] = value.strip()
    # lists
    for key in expected_list_fields:
        value = obj.get(key, [])
        if value is None:
            value = []
        elif not isinstance(value, list):
            value = [value]
        cleaned[key] = value
    return cleaned


def validate_parsed_object(obj: Dict[str, Any]) -> Tuple[Dict[str, bool], bool]:
    """Validate a parsed object and return flags and needs_review.

    Flags capture missing headwords, missing definitions and malformed
    example fields. ``needs_review`` is True if any flag is True.
    """
    flags = {
        "missing_headword": not bool(obj.get("headword")),
        "missing_definition": not bool(obj.get("definition")),
        "bad_examples": not isinstance(obj.get("examples", []), list),
    }
    needs_review = any(flags.values())
    return flags, needs_review


class GenAIParser:
    """Wrapper around an LLM client for structured extraction."""

    def __init__(self, base_url: str | None, model_name: str, system_prompt: str, parser_prompt: str, temperature: float, max_tokens: int):
        # instantiate client; base_url can be None to use default OpenAI endpoint
        if base_url:
            self.client = OpenAI(base_url=base_url)
        else:
            self.client = OpenAI()
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.parser_prompt = parser_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens

    def ask_model(self, entry_text: str) -> str:
        """Send a single request to the LLM and return the raw response."""
        user_prompt = build_user_prompt(self.parser_prompt, entry_text)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content


    def parse_entry(self, entry_id: str, entry_text: str) -> Tuple[Dict[str, Any] | None, Dict[str, bool], bool, str]:
        """Parse a single entry using the LLM.

        Returns a tuple of (parsed_data, flags, needs_review, error_message).
        On success ``parsed_data`` will contain the cleaned fields. On
        failure ``parsed_data`` is None and ``error_message`` is populated.
        """
        try:
            raw = self.ask_model(entry_text)
            parsed, parse_err = safe_parse_json(raw)
            if parsed is None:
                return None, {}, False, parse_err or "Failed to parse JSON"
            cleaned = normalize_parsed_object(parsed)
            flags, needs_review = validate_parsed_object(cleaned)
            return cleaned, flags, needs_review, ""
        except Exception as e:
            return None, {}, False, str(e)
