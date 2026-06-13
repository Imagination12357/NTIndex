"""SQLite persistence for NTIndex.

SQLite is the source of truth. JSON and HTML generated from this module are
artifacts and should be rebuilt instead of edited manually.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class VideoInput:
    title: str
    link: str
    source: str
    target: str
    game: str
    published_at: str | None = None


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            canonical_id INTEGER,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY,
            canonical_id INTEGER,
            name TEXT NOT NULL,
            game_id INTEGER NOT NULL,

            UNIQUE(name, game_id),

            FOREIGN KEY(game_id)
                REFERENCES games(id)
        );

        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY,

            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,

            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,

            published_at TEXT,
            crawled_at TEXT NOT NULL,

            FOREIGN KEY(source_id)
                REFERENCES characters(id),

            FOREIGN KEY(target_id)
                REFERENCES characters(id),

            FOREIGN KEY(game_id)
                REFERENCES games(id)
        );

        CREATE INDEX IF NOT EXISTS idx_videos_swap
        ON videos (
            game_id,
            source_id,
            target_id
        );
        """
    )
    _ensure_canonical_column(conn, "games")
    _ensure_canonical_column(conn, "characters")
    conn.commit()


def add_video(conn: sqlite3.Connection, video: VideoInput) -> bool:
    """Insert a parsed video.

    Returns True when the video was inserted and False when its link already
    existed.
    """
    if _link_exists(conn, video.link):
        return False

    game_id = get_or_create_game(conn, video.game)
    source_id = get_or_create_character(conn, video.source, game_id)
    target_id = get_or_create_character(conn, video.target, game_id)
    crawled_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO videos (
            source_id,
            target_id,
            game_id,
            title,
            link,
            published_at,
            crawled_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            target_id,
            game_id,
            video.title,
            video.link,
            video.published_at,
            crawled_at,
        ),
    )
    conn.commit()
    return True


def add_videos(conn: sqlite3.Connection, videos: Iterable[VideoInput]) -> int:
    inserted = 0
    for video in videos:
        if add_video(conn, video):
            inserted += 1
    return inserted


def get_or_create_game(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO games (name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM games WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise RuntimeError(f"failed to create game: {name}")
    game_id = int(row["id"])
    conn.execute(
        "UPDATE games SET canonical_id = id WHERE id = ? AND canonical_id IS NULL",
        (game_id,),
    )
    return game_id


def get_or_create_character(conn: sqlite3.Connection, name: str, game_id: int) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO characters (name, game_id) VALUES (?, ?)",
        (name, game_id),
    )
    row = conn.execute(
        "SELECT id FROM characters WHERE name = ? AND game_id = ?",
        (name, game_id),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"failed to create character: {name}")
    character_id = int(row["id"])
    conn.execute(
        "UPDATE characters SET canonical_id = id WHERE id = ? AND canonical_id IS NULL",
        (character_id,),
    )
    return character_id


def merge_game(conn: sqlite3.Connection, old_id: int, new_id: int) -> None:
    if old_id == new_id:
        raise ValueError("old_id and new_id must be different")
    old_row = _require_row(conn, "games", old_id)
    new_row = _require_row(conn, "games", new_id)
    old_canonical_id = int(old_row["canonical_id"] or old_row["id"])
    new_canonical_id = int(new_row["canonical_id"] or new_row["id"])

    with conn:
        conn.execute(
            """
            UPDATE videos
            SET game_id = ?
            WHERE game_id IN (
                SELECT id
                FROM games
                WHERE id = ? OR canonical_id = ?
            )
            """,
            (new_canonical_id, old_id, old_canonical_id),
        )
        conn.execute(
            """
            UPDATE games
            SET canonical_id = ?
            WHERE id = ? OR canonical_id = ?
            """,
            (new_canonical_id, old_id, old_canonical_id),
        )


def merge_character(conn: sqlite3.Connection, old_id: int, new_id: int) -> None:
    if old_id == new_id:
        raise ValueError("old_id and new_id must be different")

    old_row = _require_row(conn, "characters", old_id)
    new_row = _require_row(conn, "characters", new_id)
    old_game_id = _canonical_game_id(conn, int(old_row["game_id"]))
    new_game_id = _canonical_game_id(conn, int(new_row["game_id"]))
    if old_game_id != new_game_id:
        raise ValueError("characters must belong to the same canonical game")

    old_canonical_id = int(old_row["canonical_id"] or old_row["id"])
    new_canonical_id = int(new_row["canonical_id"] or new_row["id"])

    with conn:
        conn.execute(
            """
            UPDATE videos
            SET source_id = ?
            WHERE source_id IN (
                SELECT id
                FROM characters
                WHERE id = ? OR canonical_id = ?
            )
            """,
            (new_canonical_id, old_id, old_canonical_id),
        )
        conn.execute(
            """
            UPDATE videos
            SET target_id = ?
            WHERE target_id IN (
                SELECT id
                FROM characters
                WHERE id = ? OR canonical_id = ?
            )
            """,
            (new_canonical_id, old_id, old_canonical_id),
        )
        conn.execute(
            """
            UPDATE characters
            SET canonical_id = ?
            WHERE id = ? OR canonical_id = ?
            """,
            (new_canonical_id, old_id, old_canonical_id),
        )


def fetch_site_data(conn: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    games = [
        dict(row)
        for row in conn.execute(
            """
            SELECT canonical.id, canonical.name
            FROM games AS canonical
            WHERE canonical.id = COALESCE(canonical.canonical_id, canonical.id)
            ORDER BY canonical.name
            """
        )
    ]
    characters = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                characters.id,
                characters.name,
                COALESCE(games.canonical_id, games.id) AS game_id,
                COALESCE(characters.canonical_id, characters.id) AS canonical_id
            FROM characters
            JOIN games ON games.id = characters.game_id
            ORDER BY characters.name, characters.id
            """
        )
    ]
    videos = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                videos.id,
                videos.title,
                videos.link,
                videos.published_at,
                videos.crawled_at,
                canonical_game.id AS game_id,
                canonical_game.name AS game,
                COALESCE(source.canonical_id, source.id) AS source_id,
                canonical_source.name AS source,
                COALESCE(target.canonical_id, target.id) AS target_id,
                canonical_target.name AS target
            FROM videos
            JOIN games ON games.id = videos.game_id
            JOIN games AS canonical_game
                ON canonical_game.id = COALESCE(games.canonical_id, games.id)
            JOIN characters AS source ON source.id = videos.source_id
            JOIN characters AS canonical_source
                ON canonical_source.id = COALESCE(source.canonical_id, source.id)
            JOIN characters AS target ON target.id = videos.target_id
            JOIN characters AS canonical_target
                ON canonical_target.id = COALESCE(target.canonical_id, target.id)
            ORDER BY canonical_game.name, canonical_source.name, canonical_target.name, videos.published_at DESC, videos.id DESC
            """
        )
    ]
    game_names = _alias_names(games, "id")
    character_names = _alias_names(characters, "canonical_id")
    for video in videos:
        video["game_names"] = game_names.get(video["game_id"], [video["game"]])
        video["source_names"] = character_names.get(video["source_id"], [video["source"]])
        video["target_names"] = character_names.get(video["target_id"], [video["target"]])
        video["thumbnail_url"] = youtube_thumbnail_url(str(video["link"]))
    return {"games": games, "characters": characters, "videos": videos}


def _link_exists(conn: sqlite3.Connection, link: str) -> bool:
    row = conn.execute("SELECT 1 FROM videos WHERE link = ?", (link,)).fetchone()
    return row is not None


def _require_row(conn: sqlite3.Connection, table: str, row_id: int) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise ValueError(f"{table} row not found: {row_id}")
    return row


def _ensure_canonical_column(conn: sqlite3.Connection, table: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})")
    }
    if "canonical_id" not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN canonical_id INTEGER")
    conn.execute(f"UPDATE {table} SET canonical_id = id WHERE canonical_id IS NULL")


def _canonical_game_id(conn: sqlite3.Connection, game_id: int) -> int:
    row = _require_row(conn, "games", game_id)
    return int(row["canonical_id"] or row["id"])


def _alias_names(rows: list[dict[str, object]], key: str) -> dict[object, list[str]]:
    aliases: dict[object, list[str]] = {}
    for row in rows:
        aliases.setdefault(row[key], []).append(str(row["name"]))
    return aliases


def youtube_thumbnail_url(link: str) -> str | None:
    video_id = youtube_video_id(link)
    if video_id is None:
        return None
    return f"https://img.youtube.com/vi/{video_id}/0.jpg"


def youtube_video_id(link: str) -> str | None:
    parsed = urlparse(link)
    host = parsed.netloc.lower()
    if host.endswith("youtube.com"):
        values = parse_qs(parsed.query).get("v")
        if values and values[0]:
            return values[0]
        if parsed.path.startswith("/shorts/"):
            return _first_path_part_after(parsed.path, "shorts")
        if parsed.path.startswith("/embed/"):
            return _first_path_part_after(parsed.path, "embed")
    if host.endswith("youtu.be"):
        return parsed.path.strip("/") or None
    return None


def _first_path_part_after(path: str, prefix: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0] != prefix:
        return None
    return parts[1] or None
