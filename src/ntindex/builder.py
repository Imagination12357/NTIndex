"""Static JSON and HTML builder for NTIndex."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

from jinja2 import Environment, PackageLoader, select_autoescape

from ntindex.db import fetch_site_data


def build_site(conn, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    game_dir = output_dir / "game"
    game_dir.mkdir(parents=True, exist_ok=True)
    _copy_assets(output_dir)

    data = fetch_site_data(conn)
    search_json = json.dumps(data, ensure_ascii=False, indent=2)
    (output_dir / "search.json").write_text(search_json, encoding="utf-8")
    (output_dir / "search.js").write_text(
        f"window.NTINDEX_DATA = {search_json};\n",
        encoding="utf-8",
    )
    (output_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (output_dir / "app.js").write_text(APP_JS, encoding="utf-8")

    env = _template_env()
    index_template = env.get_template("index.html.j2")
    game_template = env.get_template("game.html.j2")
    games = _games_with_video_counts(data)

    (output_dir / "index.html").write_text(
        index_template.render(games=games, slugify=slugify),
        encoding="utf-8",
    )

    for game in games:
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


def _copy_assets(output_dir: Path) -> None:
    source_dir = Path("assets")
    if not source_dir.exists():
        return

    target_dir = output_dir / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    for asset in source_dir.iterdir():
        if asset.is_file():
            shutil.copy2(asset, target_dir / asset.name)


def _games_with_video_counts(data: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    counts: dict[object, int] = {}
    for video in data["videos"]:
        counts[video["game_id"]] = counts.get(video["game_id"], 0) + 1

    games: list[dict[str, object]] = []
    for game in data["games"]:
        game_with_count = dict(game)
        game_with_count["video_count"] = counts.get(game["id"], 0)
        games.append(game_with_count)
    return games


STYLE_CSS = """body {
  margin: 0;
  font-family: Arial, sans-serif;
  color: #171717;
  background: #f4f5f7;
}

main {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: 32px 0;
  animation: page-in 180ms ease-out both;
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
  color: inherit;
  text-decoration: none;
}

.games {
  display: grid;
  gap: 8px;
}

.game-link,
.result {
  display: block;
  padding: 12px;
  border: 1px solid #d9dde3;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  transition:
    transform 140ms ease,
    border-color 140ms ease,
    box-shadow 140ms ease,
    background-color 140ms ease;
}

.game-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.game-count {
  color: #667085;
  font-size: 14px;
  white-space: nowrap;
}

.result.has-thumbnail {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 14px;
  align-items: center;
}

.result {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
}

.result-link {
  min-width: 0;
}

.result-link.has-thumbnail {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 14px;
  align-items: center;
}

.result.has-thumbnail {
  display: grid;
  grid-template-columns: 1fr auto;
}

.thumbnail {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: 4px;
  background: #e5e7eb;
}

.thumbnail.placeholder {
  object-fit: cover;
}

.copy-link {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d9dde3;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition:
    transform 140ms ease,
    border-color 140ms ease,
    background-color 140ms ease;
}

.copy-link:hover {
  transform: translateY(-1px);
  border-color: #a7b1c2;
  background: #f8fafc;
}

.copy-link.copied {
  border-color: #5c946e;
  background: #eef8f1;
}

.copy-link.copied::after {
  content: "Copied";
  position: absolute;
  left: 50%;
  top: -28px;
  transform: translateX(-50%);
  padding: 4px 7px;
  border-radius: 4px;
  color: #fff;
  background: #1f2937;
  font-size: 12px;
  white-space: nowrap;
}

.copy-link {
  position: relative;
}

.copy-link img {
  width: 18px;
  height: 18px;
  display: block;
}

.game-link:hover,
.result:hover {
  transform: translateY(-2px);
  border-color: #a7b1c2;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
  background: #fbfcff;
}

.game-link:focus-visible,
.result-link:focus-visible,
.copy-link:focus-visible,
nav a:focus-visible {
  outline: 3px solid #8ab4f8;
  outline-offset: 3px;
}

.home-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  color: #303846;
  font-weight: 700;
  line-height: 1;
  transition: color 140ms ease;
}

.home-link span {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding-top: 1px;
}

.home-link:hover {
  color: #111827;
}

.home-icon {
  width: 18px;
  height: 18px;
  display: block;
}

.search {
  display: grid;
  grid-template-columns: 1fr auto 1fr 180px;
  align-items: end;
  gap: 12px;
  margin-bottom: 24px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

input,
select {
  min-width: 0;
  padding: 10px;
  border: 1px solid #bbb;
  border-radius: 4px;
  font: inherit;
  background: #fff;
}

.as-text {
  padding-bottom: 10px;
  color: #555;
}

.results {
  display: grid;
  gap: 10px;
}

.result-count {
  margin-bottom: 10px;
  color: #555;
  font-size: 14px;
}

.meta {
  margin-top: 4px;
  color: #666;
  font-size: 14px;
}

@keyframes page-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  main {
    animation: none;
  }

  .game-link,
  .result,
  .copy-link,
  nav a {
    transition: none;
  }

  .game-link:hover,
  .result:hover,
  .copy-link:hover {
    transform: none;
  }
}

@media (max-width: 640px) {
  .search {
    grid-template-columns: 1fr;
  }

  .as-text {
    padding-bottom: 0;
  }

  .result,
  .result.has-thumbnail {
    grid-template-columns: 1fr;
  }

  .result-link.has-thumbnail {
    grid-template-columns: 1fr;
  }

  .copy-link {
    width: 100%;
  }
}
"""


APP_JS = """async function main() {
  const thumbnailPlaceholder = "https://img.youtube.com/vi/THUMBNAIL_PLACEHOLDER/0.jpg";
  const gameId = Number(document.body.dataset.gameId);
  if (!gameId) {
    return;
  }

  const data = window.NTINDEX_DATA;
  if (!data) {
    return;
  }
  const sourceInput = document.getElementById("sourceQuery");
  const targetInput = document.getElementById("targetQuery");
  const sortInput = document.getElementById("sortMode");
  const results = document.getElementById("results");
  const resultCount = document.getElementById("resultCount");
  restoreStateFromUrl(sourceInput, targetInput, sortInput);

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
    sortVideos(videos, sortInput.value);
    resultCount.textContent = `${videos.length} result${videos.length === 1 ? "" : "s"}`;

    results.innerHTML = "";
    if (videos.length === 0) {
      results.textContent = "No videos found.";
      return;
    }

    for (const video of videos) {
      const item = document.createElement("article");
      item.className = "result";

      const link = document.createElement("a");
      link.className = "result-link";
      link.href = video.link;

      if (video.thumbnail_url) {
        link.classList.add("has-thumbnail");
        const thumbnail = document.createElement("img");
        thumbnail.className = "thumbnail";
        thumbnail.src = video.thumbnail_url;
        thumbnail.alt = "";
        thumbnail.loading = "lazy";
        thumbnail.addEventListener("error", () => {
          if (thumbnail.dataset.placeholder === "true") {
            return;
          }
          thumbnail.dataset.placeholder = "true";
          thumbnail.classList.add("placeholder");
          thumbnail.src = thumbnailPlaceholder;
        });
        link.appendChild(thumbnail);
      }

      const content = document.createElement("div");
      content.className = "result-content";

      const title = document.createElement("div");
      title.textContent = video.title;
      content.appendChild(title);

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `${video.source} → ${video.target}`;
      content.appendChild(meta);

      link.appendChild(content);
      item.appendChild(link);

      const copyButton = document.createElement("button");
      copyButton.className = "copy-link";
      copyButton.type = "button";
      copyButton.setAttribute("aria-label", `Copy link for ${video.title}`);
      copyButton.innerHTML = '<img src="../assets/copy.svg" alt="">';
      copyButton.addEventListener("click", async () => {
        const copied = await copyText(video.link);
        copyButton.setAttribute("aria-label", copied ? "Copied" : "Copy failed");
        copyButton.classList.toggle("copied", copied);
        if (copied) {
          window.clearTimeout(copyButton.copyResetTimer);
          copyButton.copyResetTimer = window.setTimeout(() => {
            copyButton.classList.remove("copied");
            copyButton.setAttribute("aria-label", `Copy link for ${video.title}`);
          }, 1400);
        }
      });
      item.appendChild(copyButton);

      results.appendChild(item);
    }
  }

  function renderAndUpdateUrl() {
    updateUrlState(sourceInput, targetInput, sortInput);
    render();
  }

  sourceInput.addEventListener("input", renderAndUpdateUrl);
  targetInput.addEventListener("input", renderAndUpdateUrl);
  sortInput.addEventListener("change", renderAndUpdateUrl);
  window.addEventListener("popstate", () => {
    restoreStateFromUrl(sourceInput, targetInput, sortInput);
    render();
  });
  render();
}

function sortVideos(videos, mode) {
  const [field, direction] = mode.split("-");
  const factor = direction === "desc" ? -1 : 1;
  videos.sort((left, right) => {
    const leftValue = String(left[field] || "").toLocaleLowerCase();
    const rightValue = String(right[field] || "").toLocaleLowerCase();
    return leftValue.localeCompare(rightValue) * factor;
  });
}

function restoreStateFromUrl(sourceInput, targetInput, sortInput) {
  const params = new URLSearchParams(window.location.search);
  sourceInput.value = params.get("source") || "";
  targetInput.value = params.get("target") || "";
  const sort = params.get("sort");
  if (sort && Array.from(sortInput.options).some((option) => option.value === sort)) {
    sortInput.value = sort;
  }
}

function updateUrlState(sourceInput, targetInput, sortInput) {
  const params = new URLSearchParams(window.location.search);
  setOptionalParam(params, "source", sourceInput.value.trim());
  setOptionalParam(params, "target", targetInput.value.trim());
  setOptionalParam(params, "sort", sortInput.value === "title-asc" ? "" : sortInput.value);
  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  window.history.replaceState(null, "", nextUrl);
}

function setOptionalParam(params, key, value) {
  if (value) {
    params.set(key, value);
    return;
  }
  params.delete(key);
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return fallbackCopyText(text);
    }
  }

  return fallbackCopyText(text);
}

function fallbackCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

main();
"""
