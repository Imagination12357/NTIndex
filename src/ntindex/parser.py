"""Title parsing for NeonTeam model-swap video titles."""

from __future__ import annotations

from dataclasses import dataclass
import re


TITLE_RE = re.compile(
    r"^\s*(?P<source>.+?)\s+as\s+(?P<target>.+?)\s*\|\s*(?P<game>.+?)\s+Model\s+Swap\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedTitle:
    source: str
    target: str
    game: str


def parse_title(title: str) -> ParsedTitle | None:
    """Parse `A as B | Game Model Swap` titles.

    Returns None when the title does not match the expected SPEC.md pattern.
    """
    match = TITLE_RE.match(title)
    if not match:
        return None

    source = _normalize_name(match.group("source"))
    target = _normalize_name(match.group("target"))
    game = _normalize_name(match.group("game"))

    if not source or not target or not game:
        return None

    return ParsedTitle(source=source, target=target, game=game)


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split())
