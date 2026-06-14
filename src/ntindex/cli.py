"""Command line interface for NTIndex."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from ntindex.builder import build_site
from ntindex.crawler import (
    load_crawl_result_from_feed_url,
    load_crawl_result_from_json,
    load_crawl_result_from_youtube_channel,
    load_crawl_result_from_ytdlp_channel,
    load_crawl_result_from_ytdlp_url,
)
from ntindex.db import (
    ParseFailureRecord,
    add_videos,
    connect,
    init_db,
    list_parse_failures,
    merge_character,
    merge_game,
    preview_merge_character,
    preview_merge_game,
    record_parse_failures,
)


DEFAULT_DB = "ntindex.sqlite3"
DEFAULT_DIST = "dist"
DEFAULT_CHANNEL_ID = "UCI4No3r3X66tSQbVgXse_MA"


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
        if args.command == "failures":
            return _failures(args)
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
    _add_crawl_source_args(crawl)

    build = subparsers.add_parser("build", help="generate static site")
    _add_dist_arg(build)

    update = subparsers.add_parser("update", help="crawl then build")
    _add_crawl_source_args(update)
    _add_dist_arg(update)

    merge = subparsers.add_parser("merge", help="merge duplicate records")
    merge.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    merge_subparsers = merge.add_subparsers(dest="merge_kind", required=True)

    merge_game_parser = merge_subparsers.add_parser("game", help="merge games")
    merge_game_parser.add_argument("old_id", type=int)
    merge_game_parser.add_argument("new_id", type=int)

    merge_character_parser = merge_subparsers.add_parser("character", help="merge characters")
    merge_character_parser.add_argument("old_id", type=int)
    merge_character_parser.add_argument("new_id", type=int)

    failures = subparsers.add_parser("failures", help="inspect parse failures")
    failures_subparsers = failures.add_subparsers(dest="failures_command", required=True)
    failures_list = failures_subparsers.add_parser("list", help="list parse failures")
    failures_list.add_argument("--all", action="store_true", help="include resolved failures")
    failures_list.add_argument("--limit", type=int, default=50, help="maximum rows to show")
    failures_list.add_argument("--json", action="store_true", help="output JSON")

    return parser


def _add_crawl_source_args(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="JSON file with video items")
    source.add_argument("--feed-url", help="YouTube Atom feed URL")
    source.add_argument("--channel-url", help="YouTube channel URL for yt-dlp")
    source.add_argument(
        "--channel-id",
        default=DEFAULT_CHANNEL_ID,
        help="YouTube channel ID",
    )
    parser.add_argument(
        "--recent",
        action="store_true",
        help="use the recent YouTube Atom feed instead of yt-dlp backfill",
    )


def _add_dist_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dist",
        "--out",
        dest="dist",
        default=DEFAULT_DIST,
        type=Path,
        help="static site output directory",
    )


def _crawl(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    result = _load_crawl_source(args)
    inserted = add_videos(conn, result.videos)
    failures = [
        ParseFailureRecord(
            link=failure.link,
            title=failure.title,
            source=failure.source,
            reason=failure.reason,
            detail=failure.detail,
            published_at=failure.published_at,
        )
        for failure in result.failures
    ]
    recorded_failures = record_parse_failures(conn, failures)
    print(f"inserted {inserted} video(s)")
    print(f"recorded {recorded_failures} parse failure(s)")
    for message in result.skipped:
        print(f"skipped: {message}", file=sys.stderr)
    return 0


def _load_crawl_source(args: argparse.Namespace):
    if args.input is not None:
        return load_crawl_result_from_json(args.input)
    if args.feed_url:
        return load_crawl_result_from_feed_url(args.feed_url)
    if args.channel_url:
        return load_crawl_result_from_ytdlp_url(args.channel_url)
    if args.recent:
        return load_crawl_result_from_youtube_channel(args.channel_id)
    if args.channel_id:
        return load_crawl_result_from_ytdlp_channel(args.channel_id)
    raise ValueError("crawl source is required")


def _build(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    build_site(conn, args.dist)
    print(f"built {args.dist}")
    return 0


def _merge(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    if args.merge_kind == "game":
        preview = preview_merge_game(conn, args.old_id, args.new_id)
        _print_merge_preview(preview)
        if not args.yes and not _confirm_merge():
            print("aborted")
            return 1
        merge_game(conn, args.old_id, args.new_id)
    elif args.merge_kind == "character":
        preview = preview_merge_character(conn, args.old_id, args.new_id)
        _print_merge_preview(preview)
        if not args.yes and not _confirm_merge():
            print("aborted")
            return 1
        merge_character(conn, args.old_id, args.new_id)
    else:
        raise ValueError(f"unsupported merge kind: {args.merge_kind}")
    print(f"merged {args.merge_kind} {args.old_id} -> {args.new_id}")
    return 0


def _failures(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    if args.failures_command == "list":
        failures = list_parse_failures(
            conn,
            include_resolved=args.all,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps([asdict(failure) for failure in failures], ensure_ascii=False, indent=2))
            return 0
        _print_failures(failures)
        return 0
    raise ValueError(f"unsupported failures command: {args.failures_command}")


def _print_failures(failures) -> None:
    if not failures:
        print("No parse failures.")
        return

    for failure in failures:
        status = "resolved" if failure.resolved_at else "unresolved"
        title = failure.title or "(missing title)"
        print(f"[{failure.id}] {status} {failure.reason} seen={failure.seen_count}")
        print(f"  title: {title}")
        print(f"  link:  {failure.link}")
        print(f"  source: {failure.source}")
        print(f"  last_seen_at: {failure.last_seen_at}")
        if failure.detail:
            print(f"  detail: {failure.detail}")
        print("")


def _print_merge_preview(preview) -> None:
    print(f"Merge {preview.kind} {preview.old_id} -> {preview.new_id}")
    print("")
    print("Old:")
    print(f"  {preview.old_id}  {preview.old_name}  canonical={preview.old_canonical_id}")
    print("New:")
    print(f"  {preview.new_id}  {preview.new_name}  canonical={preview.new_canonical_id}")
    print("")
    print("Changes:")
    if preview.kind == "game":
        print(f"  videos.game_id updated: {preview.video_game_updates}")
    else:
        print(f"  videos.source_id updated: {preview.video_source_updates}")
        print(f"  videos.target_id updated: {preview.video_target_updates}")
    print(f"  alias rows updated: {preview.alias_rows_updated}")


def _confirm_merge() -> bool:
    answer = input("Proceed? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


if __name__ == "__main__":
    raise SystemExit(main())
