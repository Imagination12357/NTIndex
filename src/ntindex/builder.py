"""Static JSON and HTML builder for NTIndex."""

from __future__ import annotations

import json
from pathlib import Path
import re

from ntindex.db import fetch_site_data


def build_site(conn, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    game_dir = output_dir / "game"
    game_dir.mkdir(parents=True, exist_ok=True)

    data = fetch_site_data(conn)
    (output_dir / "search.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (output_dir / "app.js").write_text(APP_JS, encoding="utf-8")
    (output_dir / "index.html").write_text(_render_index(data["games"]), encoding="utf-8")

    for game in data["games"]:
        slug = slugify(str(game["name"]))
        path = game_dir / f"{slug}.html"
        path.write_text(_render_game_page(game), encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "game"


def _render_index(games: list[dict[str, object]]) -> str:
    game_links = "\n".join(
        f'<a class="game-link" href="game/{slugify(str(game["name"]))}.html">{_escape(str(game["name"]))}</a>'
        for game in games
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NTIndex</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main>
    <header>
      <h1>NTIndex</h1>
      <p>NeonTeam model-swap index</p>
    </header>
    <section class="games" aria-label="Games">
      {game_links or '<p>No games indexed yet.</p>'}
    </section>
  </main>
</body>
</html>
"""


def _render_game_page(game: dict[str, object]) -> str:
    name = _escape(str(game["name"]))
    game_id = int(game["id"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} - NTIndex</title>
  <link rel="stylesheet" href="../style.css">
</head>
<body data-game-id="{game_id}">
  <main>
    <nav><a href="../index.html">NTIndex</a></nav>
    <header>
      <h1>{name}</h1>
      <p>Search source and target characters.</p>
    </header>
    <section class="search">
      <label>
        Source
        <input id="sourceQuery" type="search" autocomplete="off">
      </label>
      <span class="as-text">as</span>
      <label>
        Target
        <input id="targetQuery" type="search" autocomplete="off">
      </label>
    </section>
    <section id="results" class="results" aria-live="polite"></section>
  </main>
  <script src="../app.js"></script>
</body>
</html>
"""


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


STYLE_CSS = """body {
  margin: 0;
  font-family: Arial, sans-serif;
  color: #171717;
  background: #f7f7f7;
}

main {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0;
}

header {
  margin-bottom: 24px;
}

h1 {
  margin: 0 0 8px;
  font-size: 32px;
}

p {
  margin: 0;
  color: #555;
}

a {
  color: #064f8f;
}

.games {
  display: grid;
  gap: 8px;
}

.game-link,
.result {
  display: block;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fff;
}

.search {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: end;
  gap: 12px;
  margin-bottom: 24px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

input {
  min-width: 0;
  padding: 10px;
  border: 1px solid #bbb;
  border-radius: 4px;
  font: inherit;
}

.as-text {
  padding-bottom: 10px;
  color: #555;
}

.results {
  display: grid;
  gap: 10px;
}

.meta {
  margin-top: 4px;
  color: #666;
  font-size: 14px;
}

@media (max-width: 640px) {
  .search {
    grid-template-columns: 1fr;
  }

  .as-text {
    padding-bottom: 0;
  }
}
"""


APP_JS = """async function main() {
  const gameId = Number(document.body.dataset.gameId);
  if (!gameId) {
    return;
  }

  const response = await fetch("../search.json");
  const data = await response.json();
  const sourceInput = document.getElementById("sourceQuery");
  const targetInput = document.getElementById("targetQuery");
  const results = document.getElementById("results");

  function render() {
    const sourceQuery = sourceInput.value.trim().toLowerCase();
    const targetQuery = targetInput.value.trim().toLowerCase();
    const videos = data.videos.filter((video) => {
      if (video.game_id !== gameId) {
        return false;
      }
      const sourceOk = !sourceQuery || video.source.toLowerCase().includes(sourceQuery);
      const targetOk = !targetQuery || video.target.toLowerCase().includes(targetQuery);
      return sourceOk && targetOk;
    });

    results.innerHTML = "";
    if (videos.length === 0) {
      results.textContent = "No videos found.";
      return;
    }

    for (const video of videos) {
      const item = document.createElement("a");
      item.className = "result";
      item.href = video.link;
      item.textContent = video.title;

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${video.source} as ${video.target}`;
      item.appendChild(meta);

      results.appendChild(item);
    }
  }

  sourceInput.addEventListener("input", render);
  targetInput.addEventListener("input", render);
  render();
}

main();
"""
