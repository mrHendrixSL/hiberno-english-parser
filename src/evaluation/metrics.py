"""Evaluation metrics for parser output grounding.

This module provides a set of functions for measuring how well
extracted content from the dictionary entries is grounded in the source
text. The metrics mirror those defined in the notebook:

* Phrase containment: each extracted phrase appears verbatim in the
  source text.
* Unordered consumptive token match: multiset precision/recall allowing
  tokens to appear in any order.
* Ordered consumptive token match: similar but sensitive to ordering.

The functions return precision, recall and F1 scores as floats in the
range [0, 1], or ``None`` where the metric is undefined (e.g. when the
denominator is zero).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Tuple

from ..shared.utils import normalize_text_for_match, to_text_list


def tokenize_for_matching(text: str) -> List[str]:
    """Tokenise text into lowercase alphanumeric tokens for matching."""
    if not text:
        return []
    text = normalize_text_for_match(text)
    return re.findall(r"\b\w+\b", text)


def unordered_consumptive_match(source_value: Any, output_value: Any) -> Dict[str, Any]:
    """Compute unordered consumptive token matching statistics.

    Tokens are matched based on their counts in the source and output.
    The counts of tokens in the output are consumed by matches. Extra
    tokens contribute to false positives; missing tokens contribute to
    false negatives. Returns a dictionary with precision, recall, F1 and
    the matched, extra and missing token counters.
    """
    source_tokens: List[str] = []
    for s in to_text_list(source_value):
        source_tokens.extend(tokenize_for_matching(s))
    output_tokens: List[str] = []
    for o in to_text_list(output_value):
        output_tokens.extend(tokenize_for_matching(o))
    source_counter = Counter(source_tokens)
    output_counter = Counter(output_tokens)
    matched_counter: Counter[str] = Counter()
    for tok, out_count in output_counter.items():
        matched_counter[tok] = min(out_count, source_counter.get(tok, 0))
    matched_total = sum(matched_counter.values())
    source_total = sum(source_counter.values())
    output_total = sum(output_counter.values())
    extra_counter = output_counter - matched_counter
    missing_counter = source_counter - matched_counter
    precision = matched_total / output_total if output_total else None
    recall = matched_total / source_total if source_total else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) > 0 else None
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_tokens": matched_counter,
        "extra_tokens": extra_counter,
        "missing_tokens": missing_counter,
    }


def ordered_consumptive_match(source_value: Any, output_value: Any) -> Dict[str, Any]:
    """Compute ordered consumptive token matching statistics.

    This variant respects the ordering of tokens. It marches through the
    source tokens and attempts to match each token in turn from the
    output tokens. Matched tokens are consumed and cannot be reused.
    """
    source_tokens: List[str] = []
    for s in to_text_list(source_value):
        source_tokens.extend(tokenize_for_matching(s))
    output_tokens: List[str] = []
    for o in to_text_list(output_value):
        output_tokens.extend(tokenize_for_matching(o))
    matched = 0
    output_index = 0
    for tok in source_tokens:
        while output_index < len(output_tokens) and output_tokens[output_index] != tok:
            output_index += 1
        if output_index < len(output_tokens):
            matched += 1
            output_index += 1
    precision = matched / len(output_tokens) if output_tokens else None
    recall = matched / len(source_tokens) if source_tokens else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) > 0 else None
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_tokens": matched,
        "source_tokens": len(source_tokens),
        "output_tokens": len(output_tokens),
    }


def phrase_containment(source_value: Any, output_value: Any) -> bool:
    """Check if every extracted phrase appears verbatim in the source text."""
    source_text = normalize_text_for_match(source_value) if isinstance(source_value, str) else "\n".join([normalize_text_for_match(x) for x in to_text_list(source_value)])
    for phrase in to_text_list(output_value):
        if phrase and phrase not in source_text:
            return False
    return True
