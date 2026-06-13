"""Static JSON and HTML builder for NTIndex."""

from __future__ import annotations

import json
from pathlib import Path
import re

from jinja2 import Environment, PackageLoader, select_autoescape

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

    env = _template_env()
    index_template = env.get_template("index.html.j2")
    game_template = env.get_template("game.html.j2")

    (output_dir / "index.html").write_text(
        index_template.render(games=data["games"], slugify=slugify),
        encoding="utf-8",
    )

    for game in data["games"]:
        slug = slugify(str(game["name"]))
        path = game_dir / f"{slug}.html"
        path.write_text(game_template.render(game=game), encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "game"


def _template_env() -> Environment:
    return Environment(
        loader=PackageLoader("ntindex", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
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
      const sourceNames = video.source_names || [video.source];
      const targetNames = video.target_names || [video.target];
      const sourceOk = !sourceQuery || sourceNames.some((name) => name.toLowerCase().includes(sourceQuery));
      const targetOk = !targetQuery || targetNames.some((name) => name.toLowerCase().includes(targetQuery));
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
