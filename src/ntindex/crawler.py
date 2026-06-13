"""Input ingestion for crawl operations.

The first implementation accepts a local JSON file so parsing, persistence, and
build behavior can be developed without a YouTube API dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ntindex.db import VideoInput
from ntindex.parser import parse_title


def load_videos_from_json(path: Path) -> tuple[list[VideoInput], list[str]]:
    """Load videos from a JSON file.

    Expected item shape:
    {"title": "...", "link": "...", "published_at": "..."}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("crawl input must be a JSON array")

    videos: list[VideoInput] = []
    skipped: list[str] = []

    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            skipped.append(f"item {index}: not an object")
            continue

        title = _string_value(item, "title")
        link = _string_value(item, "link")
        if not title or not link:
            skipped.append(f"item {index}: missing title or link")
            continue

        parsed = parse_title(title)
        if parsed is None:
            skipped.append(f"item {index}: title did not match pattern")
            continue

        videos.append(
            VideoInput(
                title=title,
                link=link,
                source=parsed.source,
                target=parsed.target,
                game=parsed.game,
                published_at=_string_value(item, "published_at"),
            )
        )

    return videos, skipped


def _string_value(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
