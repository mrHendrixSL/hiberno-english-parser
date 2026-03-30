"""Helper functions for reading DOCX files.

The rule‑based parser operates on plain text paragraphs extracted from a
Microsoft Word document. This module encapsulates the dependency on
``python‑docx`` so that I/O concerns are separated from parsing logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from docx import Document

from ..shared.utils import hash_text


def extract_paragraphs(docx_path: str | Path) -> pd.DataFrame:
    """Extract non‑empty paragraphs from a DOCX file.

    Parameters
    ----------
    docx_path : str or Path
        Path to the input Word document.

    Returns
    -------
    pandas.DataFrame
        A DataFrame with columns ``para_id`` (1‑indexed integer),
        ``text`` (the stripped paragraph text) and ``text_hash`` (a SHA‑256
        hash). Empty paragraphs are skipped.
    """
    path = Path(docx_path)
    doc = Document(path)
    rows: List[Dict[str, Any]] = []
    for i, p in enumerate(doc.paragraphs, start=1):
        txt = p.text.strip()
        if txt:
            rows.append({"para_id": i, "text": txt, "text_hash": hash_text(txt)})
    return pd.DataFrame(rows)
