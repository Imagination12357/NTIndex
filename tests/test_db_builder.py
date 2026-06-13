import json

from ntindex.builder import build_site
from ntindex.db import (
    VideoInput,
    add_video,
    connect,
    fetch_site_data,
    init_db,
    merge_character,
    merge_game,
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
