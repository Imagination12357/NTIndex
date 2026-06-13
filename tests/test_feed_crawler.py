from pathlib import Path

import sys
import types

from ntindex.crawler import (
    load_videos_from_feed_xml,
    load_videos_from_youtube_channel,
    load_videos_from_ytdlp_channel,
)


def test_load_videos_from_feed_xml_extracts_matching_entries():
    xml_text = Path("examples/feed.xml").read_text(encoding="utf-8")

    videos, skipped = load_videos_from_feed_xml(xml_text)

    assert len(videos) == 2
    assert videos[0].title == "Furina as Nahida | Genshin Impact Model Swap"
    assert videos[0].link == "https://www.youtube.com/watch?v=example-furina-nahida"
    assert videos[0].source == "Furina"
    assert videos[0].target == "Nahida"
    assert videos[0].game == "Genshin Impact"
    assert skipped == ["feed entry 3: title did not match pattern"]


def test_load_videos_from_youtube_channel_builds_official_feed_url(monkeypatch):
    calls = []

    def fake_load(url):
        calls.append(url)
        return [], []

    monkeypatch.setattr("ntindex.crawler.load_videos_from_feed_url", fake_load)

    videos, skipped = load_videos_from_youtube_channel("UC_example")

    assert videos == []
    assert skipped == []
    assert calls == ["https://www.youtube.com/feeds/videos.xml?channel_id=UC_example"]


def test_load_videos_from_ytdlp_channel_extracts_matching_entries(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def extract_info(self, url, download):
            assert url == "https://www.youtube.com/channel/UC_example/videos"
            assert download is False
            return {
                "entries": [
                    {
                        "title": "Furina as Nahida | Genshin Impact Model Swap",
                        "url": "example-furina-nahida",
                        "upload_date": "20260101",
                    },
                    {
                        "title": "NeonTeam model swap showcase",
                        "url": "example-invalid-title",
                    },
                ]
            }

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)

    videos, skipped = load_videos_from_ytdlp_channel("UC_example")

    assert len(videos) == 1
    assert videos[0].link == "https://www.youtube.com/watch?v=example-furina-nahida"
    assert videos[0].published_at == "20260101"
    assert skipped == ["yt-dlp entry 2: title did not match pattern"]
