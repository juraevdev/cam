"""
License plate text cleaning helpers (Uzbekistan-oriented).
"""

from __future__ import annotations

import re
from typing import Iterable

# Keep Latin letters + digits only after cleanup.
_NON_ALNUM = re.compile(r"[^A-Z0-9]")

# Common OCR confusions on plates
_OCR_SUBSTITUTIONS = str.maketrans(
    {
        "О": "O",  # Cyrillic O
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "У": "Y",
    }
)

# Loose patterns for UZ plates, e.g. 01A123AA / 01123AAA / 10A123BC
_PLATE_CANDIDATE = re.compile(
    r"(?:"
    r"\d{2}[A-Z]\d{3}[A-Z]{2}"  # 01A123AA
    r"|"
    r"\d{2}\d{3}[A-Z]{3}"  # 01123AAA
    r"|"
    r"\d{2}[A-Z]{3}\d{3}"  # rare / foreign-like
    r")"
)


def clean_plate_text(raw: str) -> str:
    """Uppercase, strip spaces/symbols, normalize common OCR mistakes."""
    text = (raw or "").strip().upper().translate(_OCR_SUBSTITUTIONS)
    text = _NON_ALNUM.sub("", text)
    return text


def extract_best_plate(
    texts: Iterable[str],
    *,
    min_len: int = 6,
    max_len: int = 12,
) -> str | None:
    """
    From OCR snippets, return the most plausible plate string.
    Prefers regex matches; falls back to longest cleaned token.
    """
    cleaned_tokens: list[str] = []
    for raw in texts:
        cleaned = clean_plate_text(raw)
        if not cleaned:
            continue
        cleaned_tokens.append(cleaned)

        match = _PLATE_CANDIDATE.search(cleaned)
        if match:
            return match.group(0)

    # Join fragments in several orders (OCR often splits "25 A123 DA")
    joined = clean_plate_text("".join(cleaned_tokens))
    match = _PLATE_CANDIDATE.search(joined)
    if match:
        return match.group(0)

    # Longest-first join helps when noise tokens are short
    by_len = sorted(cleaned_tokens, key=len, reverse=True)
    joined_len = clean_plate_text("".join(by_len))
    match = _PLATE_CANDIDATE.search(joined_len)
    if match:
        return match.group(0)

    candidates = [t for t in cleaned_tokens if min_len <= len(t) <= max_len]
    if not candidates:
        return None
    return max(candidates, key=len)
