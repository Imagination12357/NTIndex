import json
import subprocess
import sys

from ntindex.crawler import CrawlResult


def test_cli_crawl_and_build_with_example_input(tmp_path):
    db_path = tmp_path / "ntindex.sqlite3"
    out_dir = tmp_path / "dist"

    crawl = subprocess.run(
        [
            sys.executable,
            "-m",
            "ntindex.cli",
            "--db",
            str(db_path),
            "crawl",
            "--input",
            "examples/videos.json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert crawl.returncode == 0
    assert "inserted 2 video(s)" in crawl.stdout
    assert "recorded 1 parse failure(s)" in crawl.stdout
    assert "skipped: item 4: title did not match pattern" in crawl.stderr

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "ntindex.cli",
            "--db",
            str(db_path),
            "build",
            "--dist",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert build.returncode == 0
    assert (out_dir / "index.html").exists()
    assert (out_dir / "game" / "genshin-impact.html").exists()
    assert (out_dir / "game" / "honkai-star-rail.html").exists()

    search_data = json.loads((out_dir / "search.json").read_text(encoding="utf-8"))
    assert [video["title"] for video in search_data["videos"]] == [
        "Furina as Nahida | Genshin Impact Model Swap",
        "March 7th as Firefly | Honkai Star Rail Model Swap",
    ]


def test_cli_update_runs_crawl_then_build(tmp_path):
    db_path = tmp_path / "ntindex.sqlite3"
    out_dir = tmp_path / "dist"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ntindex.cli",
            "--db",
            str(db_path),
            "update",
            "--input",
            "examples/videos.json",
            "--dist",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "inserted 2 video(s)" in result.stdout
    assert "recorded 1 parse failure(s)" in result.stdout
    assert f"built {out_dir}" in result.stdout
    assert (out_dir / "search.json").exists()


def test_cli_crawl_uses_default_channel_id(monkeypatch, tmp_path):
    calls = []

    def fake_load(channel_id):
        calls.append(channel_id)
        return CrawlResult(videos=[], failures=[], skipped=[])

    monkeypatch.setattr("ntindex.cli.load_crawl_result_from_ytdlp_channel", fake_load)

    from ntindex.cli import main

    result = main(["--db", str(tmp_path / "ntindex.sqlite3"), "crawl"])

    assert result == 0
    assert calls == ["UCI4No3r3X66tSQbVgXse_MA"]


def test_cli_crawl_recent_uses_rss_channel_id(monkeypatch, tmp_path):
    calls = []

    def fake_load(channel_id):
        calls.append(channel_id)
        return CrawlResult(videos=[], failures=[], skipped=[])

    monkeypatch.setattr("ntindex.cli.load_crawl_result_from_youtube_channel", fake_load)

    from ntindex.cli import main

    result = main(["--db", str(tmp_path / "ntindex.sqlite3"), "crawl", "--recent"])

    assert result == 0
    assert calls == ["UCI4No3r3X66tSQbVgXse_MA"]
