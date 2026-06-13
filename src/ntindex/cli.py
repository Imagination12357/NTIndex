"""Command line interface for NTIndex."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ntindex.builder import build_site
from ntindex.crawler import load_videos_from_json
from ntindex.db import add_videos, connect, init_db, merge_character, merge_game


DEFAULT_DB = "ntindex.sqlite3"
DEFAULT_DIST = "dist"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "crawl":
            return _crawl(args)
        if args.command == "build":
            return _build(args)
        if args.command == "update":
            crawl_code = _crawl(args)
            if crawl_code != 0:
                return crawl_code
            return _build(args)
        if args.command == "merge":
            return _merge(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntindex")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")

    subparsers = parser.add_subparsers(dest="command")

    crawl = subparsers.add_parser("crawl", help="ingest videos")
    crawl.add_argument("--input", required=True, type=Path, help="JSON file with video items")

    build = subparsers.add_parser("build", help="generate static site")
    build.add_argument("--out", default=DEFAULT_DIST, type=Path, help="output directory")

    update = subparsers.add_parser("update", help="crawl then build")
    update.add_argument("--input", required=True, type=Path, help="JSON file with video items")
    update.add_argument("--out", default=DEFAULT_DIST, type=Path, help="output directory")

    merge = subparsers.add_parser("merge", help="merge duplicate records")
    merge_subparsers = merge.add_subparsers(dest="merge_kind", required=True)

    merge_game_parser = merge_subparsers.add_parser("game", help="merge games")
    merge_game_parser.add_argument("old_id", type=int)
    merge_game_parser.add_argument("new_id", type=int)

    merge_character_parser = merge_subparsers.add_parser("character", help="merge characters")
    merge_character_parser.add_argument("old_id", type=int)
    merge_character_parser.add_argument("new_id", type=int)

    return parser


def _crawl(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    videos, skipped = load_videos_from_json(args.input)
    inserted = add_videos(conn, videos)
    print(f"inserted {inserted} video(s)")
    for message in skipped:
        print(f"skipped: {message}", file=sys.stderr)
    return 0


def _build(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    build_site(conn, args.out)
    print(f"built {args.out}")
    return 0


def _merge(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    if args.merge_kind == "game":
        merge_game(conn, args.old_id, args.new_id)
    elif args.merge_kind == "character":
        merge_character(conn, args.old_id, args.new_id)
    else:
        raise ValueError(f"unsupported merge kind: {args.merge_kind}")
    print(f"merged {args.merge_kind} {args.old_id} -> {args.new_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
