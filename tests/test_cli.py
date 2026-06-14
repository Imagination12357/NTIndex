import json
import subprocess
import sys

from ntindex.crawler import CrawlResult
from ntindex.db import (
    ParseFailureRecord,
    VideoInput,
    add_video,
    connect,
    init_db,
    record_parse_failures,
)


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


def test_cli_merge_requires_confirmation_by_default(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "ntindex.sqlite3"
    conn = connect(str(db_path))
    init_db(conn)
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Impact Model Swap",
            link="https://example.test/genshin-impact",
            source="Furina",
            target="Nahida",
            game="Genshin Impact",
        ),
    )
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Model Swap",
            link="https://example.test/genshin",
            source="Furina",
            target="Nahida",
            game="Genshin",
        ),
    )
    old_id = conn.execute("SELECT id FROM games WHERE name = 'Genshin'").fetchone()[0]
    new_id = conn.execute("SELECT id FROM games WHERE name = 'Genshin Impact'").fetchone()[0]
    conn.close()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    from ntindex.cli import main

    result = main(["--db", str(db_path), "merge", "game", str(old_id), str(new_id)])

    output = capsys.readouterr().out
    assert result == 1
    assert "Proceed? [y/N]:" not in output
    assert "aborted" in output


def test_cli_merge_yes_skips_confirmation(tmp_path, capsys):
    db_path = tmp_path / "ntindex.sqlite3"
    conn = connect(str(db_path))
    init_db(conn)
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Impact Model Swap",
            link="https://example.test/genshin-impact",
            source="Furina",
            target="Nahida",
            game="Genshin Impact",
        ),
    )
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Model Swap",
            link="https://example.test/genshin",
            source="Furina",
            target="Nahida",
            game="Genshin",
        ),
    )
    old_id = conn.execute("SELECT id FROM games WHERE name = 'Genshin'").fetchone()[0]
    new_id = conn.execute("SELECT id FROM games WHERE name = 'Genshin Impact'").fetchone()[0]
    conn.close()

    from ntindex.cli import main

    result = main(["--db", str(db_path), "merge", "--yes", "game", str(old_id), str(new_id)])

    output = capsys.readouterr().out
    assert result == 0
    assert "videos.game_id updated: 1" in output
    assert f"merged game {old_id} -> {new_id}" in output


def test_cli_failures_list_outputs_unresolved_failures(tmp_path, capsys):
    db_path = tmp_path / "ntindex.sqlite3"
    conn = connect(str(db_path))
    init_db(conn)
    record_parse_failures(
        conn,
        [
            ParseFailureRecord(
                link="https://example.test/bad",
                title="Bad title",
                source="json",
                reason="title_not_matched",
            )
        ],
    )
    conn.close()

    from ntindex.cli import main

    result = main(["--db", str(db_path), "failures", "list"])

    output = capsys.readouterr().out
    assert result == 0
    assert "title_not_matched" in output
    assert "https://example.test/bad" in output


def test_cli_failures_list_json_outputs_json(tmp_path, capsys):
    db_path = tmp_path / "ntindex.sqlite3"
    conn = connect(str(db_path))
    init_db(conn)
    record_parse_failures(
        conn,
        [
            ParseFailureRecord(
                link="https://example.test/bad",
                title="Bad title",
                source="json",
                reason="title_not_matched",
            )
        ],
    )
    conn.close()

    from ntindex.cli import main

    result = main(["--db", str(db_path), "failures", "list", "--json"])

    output = capsys.readouterr().out
    assert result == 0
    assert json.loads(output)[0]["link"] == "https://example.test/bad"
