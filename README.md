# NTIndex

NTIndex is a static site generator for NeonTeam model-swap videos.

It collects video metadata, stores the normalized source data in SQLite, and
builds static JSON and HTML files for browsing and searching.

SQLite is the source of truth. Files under `dist/` are generated artifacts.

## Requirements

- Python 3.11+
- uv

## Setup

```powershell
uv venv
uv sync --dev
```

## Common Commands

### Crawl Videos

Default crawl uses `yt-dlp` against the configured NeonTeam channel.

```powershell
uv run ntindex crawl
```

Default values:

- `--db`: `ntindex.sqlite3`
- `--channel-id`: `UCI4No3r3X66tSQbVgXse_MA`

Use a different channel ID:

```powershell
uv run ntindex crawl --channel-id UC_other
```

Use a channel URL directly:

```powershell
uv run ntindex crawl --channel-url "https://www.youtube.com/@somechannel/videos"
```

Use YouTube RSS/Atom for recent uploads only:

```powershell
uv run ntindex crawl --recent
```

Use a specific feed URL:

```powershell
uv run ntindex crawl --feed-url "https://www.youtube.com/feeds/videos.xml?channel_id=UC_other"
```

Import local JSON:

```powershell
uv run ntindex crawl --input examples/videos.json
```

Expected JSON item shape:

```json
{
  "title": "Furina as Nahida | Genshin Impact Model Swap",
  "link": "https://www.youtube.com/watch?v=example",
  "published_at": "2026-01-01T00:00:00Z"
}
```

Only titles matching this pattern are indexed:

```text
A as B | Game Model Swap
```

### Build Static Site

```powershell
uv run ntindex build
```

Default output directory:

```text
dist/
```

Use a different output directory:

```powershell
uv run ntindex build --dist public
```

Generated files include:

```text
dist/
├── index.html
├── search.json
├── style.css
├── app.js
└── game/
    └── <game-slug>.html
```

### Update

Run crawl, then build:

```powershell
uv run ntindex update
```

Use RSS for recent uploads:

```powershell
uv run ntindex update --recent
```

Use a custom output directory:

```powershell
uv run ntindex update --dist public
```

## Merge

Merge commands use canonical IDs. Rows are not deleted.
Before applying changes, merge commands print a summary and ask for confirmation.

- `id` identifies the actual stored row.
- `canonical_id` identifies the representative row used for search and build output.
- Merge updates video rows to the canonical target ID.
- Build output still includes merged names as searchable aliases.

Important exception:

- `characters.game_id` is not rewritten by `merge game`.
- Character rows keep their original game row so alias names remain traceable.
- Search and build output still resolve those games through `games.canonical_id`.
- This avoids `UNIQUE(name, game_id)` conflicts when both merged games already contain the same character name.

In short, video references are normalized after merge, but character alias rows keep their original game ownership.

### Merge Games

```powershell
uv run ntindex merge game <old_id> <new_id>
```

Example:

```powershell
uv run ntindex merge game 12 3
```

This makes game `12` resolve to the same canonical game as `3`.

Skip the confirmation prompt:

```powershell
uv run ntindex merge --yes game 12 3
```

### Merge Characters

```powershell
uv run ntindex merge character <old_id> <new_id>
```

Example:

```powershell
uv run ntindex merge character 51 8
```

Characters can be merged only when they belong to the same canonical game.

Skip the confirmation prompt:

```powershell
uv run ntindex merge --yes character 51 8
```

Merged names remain searchable through `search.json` alias fields:

- `source_names`
- `target_names`

## Parse Failures

NTIndex records titles that were crawled but could not be parsed into the
`A as B | Game Model Swap` shape.

List unresolved parse failures:

```powershell
uv run ntindex failures list
```

Filter by review status:

```powershell
uv run ntindex failures list --status unreviewed
uv run ntindex failures list --status ignored
uv run ntindex failures list --status needs_parser
```

Include resolved failures:

```powershell
uv run ntindex failures list --all
```

Limit the number of rows:

```powershell
uv run ntindex failures list --limit 20
```

Output JSON:

```powershell
uv run ntindex failures list --json
```

Set review status:

```powershell
uv run ntindex failures review <failure_id> ignored
uv run ntindex failures review <failure_id> needs_parser --note "parser candidate"
uv run ntindex failures review <failure_id> unreviewed
```

Review statuses:

- `unreviewed`: not checked yet
- `ignored`: intentionally outside the current `A as B` data model
- `needs_parser`: likely worth supporting with parser changes

## Development

Run tests:

```powershell
uv run pytest
```

Current tests cover:

- title parsing
- SQLite insertion and duplicate skipping
- static site build output
- CLI crawl/build/update paths
- RSS feed parsing
- `yt-dlp` metadata parsing
- canonical merge behavior

## Project Notes

- `SPEC.md` is the product specification.
- `README.md` is the usage guide.
- `dist/` is generated and ignored by git.
- `ntindex.sqlite3` is local runtime data and ignored by git.
- `uv.lock` should be committed for reproducible installs.
