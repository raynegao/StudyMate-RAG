"""Normalize model citation markers to the canonical ``[Sn]`` form used across the app."""

from __future__ import annotations

import re

LABEL = re.compile(r"S(\d+)", re.IGNORECASE)
# One bracket holding several labels, e.g. [S6, S16, S17], [S6、S16], [S6; S16] or [S6 S16].
GROUPED = re.compile(r"\[\s*S\d+(?:\s*(?:[,，、;；/]\s*)?S\d+)+\s*\]", re.IGNORECASE)


def normalize_citations(text: str) -> str:
    """Rewrite grouped citation brackets into adjacent single markers.

    DeepSeek writes ``[S1][S2]``; Gemini often writes ``[S1, S2]``. The citation checks,
    the API contract and the reading page understand one label per bracket, so a grouped
    form would otherwise count as no citation at all and could turn a supported answer
    into a refusal.
    """

    def split(match: re.Match) -> str:
        return "".join(f"[S{int(number)}]" for number in LABEL.findall(match.group(0)))

    return GROUPED.sub(split, text)
