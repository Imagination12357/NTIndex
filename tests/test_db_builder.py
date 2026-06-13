import json

from ntindex.builder import build_site
from ntindex.db import VideoInput, add_video, connect, init_db, merge_character


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
        assert "same game" in str(exc)
    else:
        raise AssertionError("merge_character should reject cross-game merges")
