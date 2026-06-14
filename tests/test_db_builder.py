import json

from ntindex.builder import build_site
from ntindex.db import (
    ParseFailureRecord,
    VideoInput,
    add_video,
    connect,
    fetch_site_data,
    init_db,
    list_parse_failures,
    merge_character,
    merge_game,
    preview_merge_character,
    preview_merge_game,
    record_parse_failures,
    youtube_thumbnail_url,
    youtube_video_id,
)


def test_add_video_creates_related_records_and_skips_duplicate(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)

    video = VideoInput(
        title="Furina as Nahida | Genshin Impact Model Swap",
        link="https://example.test/video",
        source="Furina",
        target="Nahida",
        game="Genshin Impact",
    )

    assert add_video(conn, video) is True
    assert add_video(conn, video) is False

    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 1


def test_build_site_writes_search_json_and_game_page(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Impact Model Swap",
            link="https://example.test/video",
            source="Furina",
            target="Nahida",
            game="Genshin Impact",
        ),
    )

    out = tmp_path / "dist"
    build_site(conn, out)

    data = json.loads((out / "search.json").read_text(encoding="utf-8"))
    assert data["videos"][0]["source"] == "Furina"
    assert "window.NTINDEX_DATA" in (out / "search.js").read_text(encoding="utf-8")
    assert "1 videos" in (out / "index.html").read_text(encoding="utf-8")
    assert 'id="resultCount"' in (
        out / "game" / "genshin-impact.html"
    ).read_text(encoding="utf-8")
    assert (out / "index.html").exists()
    assert (out / "game" / "genshin-impact.html").exists()
    assert (out / "assets" / "home.svg").exists()
    assert (out / "assets" / "copy.svg").exists()


def test_merge_character_requires_same_game(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    genshin = conn.execute("INSERT INTO games (name) VALUES ('Genshin')").lastrowid
    honkai = conn.execute("INSERT INTO games (name) VALUES ('Honkai')").lastrowid
    old_id = conn.execute(
        "INSERT INTO characters (name, game_id) VALUES ('A', ?)",
        (genshin,),
    ).lastrowid
    new_id = conn.execute(
        "INSERT INTO characters (name, game_id) VALUES ('A', ?)",
        (honkai,),
    ).lastrowid
    conn.commit()

    try:
        merge_character(conn, old_id, new_id)
    except ValueError as exc:
        assert "same canonical game" in str(exc)
    else:
        raise AssertionError("merge_character should reject cross-game merges")


def test_merge_game_keeps_rows_and_uses_canonical_game_for_build(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
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
    preview = preview_merge_game(conn, old_id, new_id)
    assert preview.video_game_updates == 1
    assert preview.alias_rows_updated == 1

    merge_game(conn, old_id, new_id)

    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2
    assert {
        row[0]
        for row in conn.execute("SELECT DISTINCT game_id FROM videos")
    } == {new_id}
    data = fetch_site_data(conn)
    assert data["games"] == [{"id": new_id, "name": "Genshin Impact"}]
    assert {video["game_id"] for video in data["videos"]} == {new_id}


def test_merge_character_keeps_alias_names_searchable(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    add_video(
        conn,
        VideoInput(
            title="Lesser Lord Kusanali as Furina | Genshin Impact Model Swap",
            link="https://example.test/kusanali-furina",
            source="Lesser Lord Kusanali",
            target="Furina",
            game="Genshin Impact",
        ),
    )
    add_video(
        conn,
        VideoInput(
            title="Nahida as Furina | Genshin Impact Model Swap",
            link="https://example.test/nahida-furina",
            source="Nahida",
            target="Furina",
            game="Genshin Impact",
        ),
    )

    old_id = conn.execute(
        "SELECT id FROM characters WHERE name = 'Lesser Lord Kusanali'"
    ).fetchone()[0]
    new_id = conn.execute("SELECT id FROM characters WHERE name = 'Nahida'").fetchone()[0]
    preview = preview_merge_character(conn, old_id, new_id)
    assert preview.video_source_updates == 1
    assert preview.video_target_updates == 0
    assert preview.alias_rows_updated == 1

    merge_character(conn, old_id, new_id)

    assert conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 3
    assert {
        row[0]
        for row in conn.execute("SELECT DISTINCT source_id FROM videos")
    } == {new_id}
    data = fetch_site_data(conn)
    videos = {video["link"]: video for video in data["videos"]}
    assert videos["https://example.test/kusanali-furina"]["source_id"] == new_id
    assert videos["https://example.test/kusanali-furina"]["source"] == "Nahida"
    assert set(videos["https://example.test/kusanali-furina"]["source_names"]) == {
        "Lesser Lord Kusanali",
        "Nahida",
    }


def test_youtube_thumbnail_url_extracts_video_id():
    assert youtube_video_id("https://www.youtube.com/watch?v=abc123") == "abc123"
    assert youtube_video_id("https://youtu.be/abc123") == "abc123"
    assert youtube_video_id("https://www.youtube.com/shorts/abc123") == "abc123"
    assert youtube_video_id("https://www.youtube.com/embed/abc123") == "abc123"
    assert youtube_video_id("https://example.test/video") is None
    assert (
        youtube_thumbnail_url("https://www.youtube.com/watch?v=abc123")
        == "https://img.youtube.com/vi/abc123/0.jpg"
    )


def test_record_parse_failures_upserts_by_link(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    failure = ParseFailureRecord(
        link="https://example.test/bad",
        title="Bad title",
        source="json",
        reason="title_not_matched",
        detail="title did not match pattern",
        published_at="2026-01-01T00:00:00Z",
    )

    assert record_parse_failures(conn, [failure]) == 1
    assert record_parse_failures(conn, [failure]) == 1

    row = conn.execute(
        "SELECT link, title, source, reason, seen_count, resolved_at FROM parse_failures"
    ).fetchone()
    assert dict(row) == {
        "link": "https://example.test/bad",
        "title": "Bad title",
        "source": "json",
        "reason": "title_not_matched",
        "seen_count": 2,
        "resolved_at": None,
    }


def test_add_video_resolves_existing_parse_failure(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    link = "https://example.test/video"
    record_parse_failures(
        conn,
        [
            ParseFailureRecord(
                link=link,
                title="Bad title",
                source="json",
                reason="title_not_matched",
            )
        ],
    )

    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Impact Model Swap",
            link=link,
            source="Furina",
            target="Nahida",
            game="Genshin Impact",
        ),
    )

    row = conn.execute("SELECT resolved_at FROM parse_failures WHERE link = ?", (link,)).fetchone()
    assert row["resolved_at"] is not None


def test_list_parse_failures_excludes_resolved_by_default(tmp_path):
    conn = connect(str(tmp_path / "ntindex.sqlite3"))
    init_db(conn)
    record_parse_failures(
        conn,
        [
            ParseFailureRecord(
                link="https://example.test/unresolved",
                title="Bad title",
                source="json",
                reason="title_not_matched",
            ),
            ParseFailureRecord(
                link="https://example.test/resolved",
                title="Old bad title",
                source="json",
                reason="title_not_matched",
            ),
        ],
    )
    add_video(
        conn,
        VideoInput(
            title="Furina as Nahida | Genshin Impact Model Swap",
            link="https://example.test/resolved",
            source="Furina",
            target="Nahida",
            game="Genshin Impact",
        ),
    )

    unresolved = list_parse_failures(conn)
    all_failures = list_parse_failures(conn, include_resolved=True)

    assert [failure.link for failure in unresolved] == ["https://example.test/unresolved"]
    assert {failure.link for failure in all_failures} == {
        "https://example.test/unresolved",
        "https://example.test/resolved",
    }
