"""Input ingestion for crawl operations.

The first implementation accepts a local JSON file so parsing, persistence, and
build behavior can be developed without a YouTube API dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from ntindex.db import VideoInput
from ntindex.parser import parse_title

YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/channel/{channel_id}/videos"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


@dataclass(frozen=True)
class ParseFailureInput:
    link: str
    title: str | None
    source: str
    reason: str
    detail: str | None = None
    published_at: str | None = None


@dataclass(frozen=True)
class CrawlResult:
    videos: list[VideoInput]
    failures: list[ParseFailureInput]
    skipped: list[str]


def load_videos_from_json(path: Path) -> tuple[list[VideoInput], list[str]]:
    result = load_crawl_result_from_json(path)
    return result.videos, result.skipped


def load_crawl_result_from_json(path: Path) -> CrawlResult:
    """Load videos from a JSON file.

    Expected item shape:
    {"title": "...", "link": "...", "published_at": "..."}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("crawl input must be a JSON array")

    videos: list[VideoInput] = []
    failures: list[ParseFailureInput] = []
    skipped: list[str] = []

    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            skipped.append(f"item {index}: not an object")
            continue

        title = _string_value(item, "title")
        link = _string_value(item, "link")
        if not title or not link:
            skipped.append(f"item {index}: missing title or link")
            if link:
                failures.append(
                    ParseFailureInput(
                        link=link,
                        title=title,
                        source="json",
                        reason="missing_title",
                        detail=f"item {index}: missing title or link",
                        published_at=_string_value(item, "published_at"),
                    )
                )
            continue

        parsed = parse_title(title)
        if parsed is None:
            skipped.append(f"item {index}: title did not match pattern")
            failures.append(
                ParseFailureInput(
                    link=link,
                    title=title,
                    source="json",
                    reason="title_not_matched",
                    detail=f"item {index}: title did not match pattern",
                    published_at=_string_value(item, "published_at"),
                )
            )
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

    return CrawlResult(videos=videos, failures=failures, skipped=skipped)


def load_videos_from_youtube_channel(channel_id: str) -> tuple[list[VideoInput], list[str]]:
    url = f"{YOUTUBE_FEED_URL}?{urlencode({'channel_id': channel_id})}"
    return load_videos_from_feed_url(url)


def load_crawl_result_from_youtube_channel(channel_id: str) -> CrawlResult:
    url = f"{YOUTUBE_FEED_URL}?{urlencode({'channel_id': channel_id})}"
    return load_crawl_result_from_feed_url(url)


def load_videos_from_ytdlp_channel(channel_id: str) -> tuple[list[VideoInput], list[str]]:
    return load_videos_from_ytdlp_url(YOUTUBE_CHANNEL_URL.format(channel_id=channel_id))


def load_crawl_result_from_ytdlp_channel(channel_id: str) -> CrawlResult:
    return load_crawl_result_from_ytdlp_url(YOUTUBE_CHANNEL_URL.format(channel_id=channel_id))


def load_videos_from_ytdlp_url(url: str) -> tuple[list[VideoInput], list[str]]:
    result = load_crawl_result_from_ytdlp_url(url)
    return result.videos, result.skipped


def load_crawl_result_from_ytdlp_url(url: str) -> CrawlResult:
    from yt_dlp import YoutubeDL

    options = {
        "extract_flat": True,
        "quiet": True,
        "skip_download": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not isinstance(entries, list):
        raise ValueError("yt-dlp result did not contain a video list")

    videos: list[VideoInput] = []
    failures: list[ParseFailureInput] = []
    skipped: list[str] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            skipped.append(f"yt-dlp entry {index}: not an object")
            continue

        title = _string_value(entry, "title")
        link = _entry_video_url(entry)
        published_at = _entry_published_at(entry)

        if not title or not link:
            skipped.append(f"yt-dlp entry {index}: missing title or link")
            if link:
                failures.append(
                    ParseFailureInput(
                        link=link,
                        title=title,
                        source="yt-dlp",
                        reason="missing_title",
                        detail=f"yt-dlp entry {index}: missing title or link",
                        published_at=published_at,
                    )
                )
            continue

        parsed = parse_title(title)
        if parsed is None:
            skipped.append(f"yt-dlp entry {index}: title did not match pattern")
            failures.append(
                ParseFailureInput(
                    link=link,
                    title=title,
                    source="yt-dlp",
                    reason="title_not_matched",
                    detail=f"yt-dlp entry {index}: title did not match pattern",
                    published_at=published_at,
                )
            )
            continue

        videos.append(
            VideoInput(
                title=title,
                link=link,
                source=parsed.source,
                target=parsed.target,
                game=parsed.game,
                published_at=published_at,
            )
        )

    return CrawlResult(videos=videos, failures=failures, skipped=skipped)


def load_videos_from_feed_url(url: str) -> tuple[list[VideoInput], list[str]]:
    result = load_crawl_result_from_feed_url(url)
    return result.videos, result.skipped


def load_crawl_result_from_feed_url(url: str) -> CrawlResult:
    with urlopen(url, timeout=30) as response:
        xml_text = response.read().decode("utf-8")
    return load_crawl_result_from_feed_xml(xml_text)


def load_videos_from_feed_xml(xml_text: str) -> tuple[list[VideoInput], list[str]]:
    result = load_crawl_result_from_feed_xml(xml_text)
    return result.videos, result.skipped


def load_crawl_result_from_feed_xml(xml_text: str) -> CrawlResult:
    root = ET.fromstring(xml_text)
    videos: list[VideoInput] = []
    failures: list[ParseFailureInput] = []
    skipped: list[str] = []

    for index, entry in enumerate(root.findall(f"{ATOM_NS}entry"), start=1):
        title = _entry_text(entry, f"{ATOM_NS}title")
        video_id = _entry_text(entry, f"{YT_NS}videoId")
        published_at = _entry_text(entry, f"{ATOM_NS}published")
        link = _entry_link(entry) or _youtube_watch_url(video_id)

        if not title or not link:
            skipped.append(f"feed entry {index}: missing title or link")
            if link:
                failures.append(
                    ParseFailureInput(
                        link=link,
                        title=title,
                        source="rss",
                        reason="missing_title",
                        detail=f"feed entry {index}: missing title or link",
                        published_at=published_at,
                    )
                )
            continue

        parsed = parse_title(title)
        if parsed is None:
            skipped.append(f"feed entry {index}: title did not match pattern")
            failures.append(
                ParseFailureInput(
                    link=link,
                    title=title,
                    source="rss",
                    reason="title_not_matched",
                    detail=f"feed entry {index}: title did not match pattern",
                    published_at=published_at,
                )
            )
            continue

        videos.append(
            VideoInput(
                title=title,
                link=link,
                source=parsed.source,
                target=parsed.target,
                game=parsed.game,
                published_at=published_at,
            )
        )

    return CrawlResult(videos=videos, failures=failures, skipped=skipped)


def _string_value(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _entry_text(entry: ET.Element, name: str) -> str | None:
    element = entry.find(name)
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _entry_link(entry: ET.Element) -> str | None:
    for link in entry.findall(f"{ATOM_NS}link"):
        href = link.attrib.get("href")
        if href:
            return href
    return None


def _youtube_watch_url(video_id: str | None) -> str | None:
    if not video_id:
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def _entry_video_url(entry: dict[str, Any]) -> str | None:
    for key in ("webpage_url", "url"):
        value = _string_value(entry, key)
        if not value:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return _youtube_watch_url(value)
    return _youtube_watch_url(_string_value(entry, "id"))


def _entry_published_at(entry: dict[str, Any]) -> str | None:
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, int):
        return str(timestamp)
    return _string_value(entry, "upload_date") or _string_value(entry, "published_at")
