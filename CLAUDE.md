# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A local-only tool for authoring and rendering programming-tutorial videos from a YAML slide script. The full intended system is described in `tutorial_video_pipeline_spec.md` at the repo root — read it for the complete feature set (Pillow renderer, Pygments/Shiki syntax highlighting, Piper/ElevenLabs TTS, FFmpeg muxing, full web authoring tool). **Only a slice of that spec is implemented so far**: the slide CRUD editor (`backend/` + `frontend/`). There is no renderer, no audio, no transitions, and no video export yet.

## Commands

Run both dev servers together (standard way to develop):
```bash
./dev.sh
```
Stops both cleanly on Ctrl+C, including uvicorn's reload-worker subprocess and Vite's node subprocess.

Backend only:
```bash
cd backend && uv run uvicorn main:app --reload --port 8000
```

Frontend only:
```bash
cd frontend && bun run dev      # dev server
cd frontend && bun run build    # production build
cd frontend && bun run lint     # oxlint
```

Dependencies:
```bash
cd backend && uv add <package>      # not pip
cd frontend && bun add <package>    # not npm — Node itself isn't installed in this project's dev environment
```

Tests: there is no automated test suite in this repo, by deliberate choice. Verify backend logic with one-off `uv run python -c "..."` snippets or `curl` against the running server. Verify the frontend visually — see "Verifying UI changes" below.

## Architecture

### YAML on disk, JSON over the wire

This is the central design decision, and the reason `backend/parser.py` exists. The on-disk script file keeps the spec's YAML format with inline `@viewport`/`@highlight` markers — chosen because it's git-diffable and hand-editable, and because moving marker positions out of the text into separate fields (e.g. a `highlighted_lines` array) would create a class of bugs where line numbers silently desync from edits. The HTTP API, however, speaks plain structured JSON, validated via Pydantic discriminated unions.

- `backend/models.py` — `CodeSlide`, `ImageSlide`, and `Slide = Annotated[Union[CodeSlide, ImageSlide], Field(discriminator="type")]`. This is the wire/validation shape.
- `backend/parser.py` — the only place that translates between the two formats: `parse_script(text) -> list[Slide]` and `serialize_script(slides) -> text`. `split_blocks()` handles splitting the script on `---`-delimited frontmatter/body pairs.
- Marker-stripping (turning `@viewport`/`@highlight` into line positions a renderer could use) is **not implemented yet** — the `code` field carries marker text through verbatim. That logic belongs to a future renderer milestone, not this layer, since nothing consumes it yet.

### The backend is storage-agnostic — no project/file management

`backend/main.py` exposes exactly two routes, `GET /api/file?path=...` and `POST /api/file`, both taking an explicit filesystem path. There is no project list, no metadata file, no database, and no "current project" concept. The filename itself (minus extension) is the slide script's title, computed client-side from `path` — never stored or sent by the backend.

### Frontend state shape

`frontend/src/App.jsx` holds `path`, `slides`, `selectedIndex`, `status` as its only state. `SlideList.jsx` renders the sidebar (add/select/delete); `SlideEditor.jsx` renders the form for whichever slide is selected, branching on `slide.type`. Each slide object carries a client-only `_key` (`crypto.randomUUID()`, assigned on creation and on load) used as the React list `key` — it's stripped out of the payload before being POSTed to the backend. (Array-index keys were tried first and replaced after checking against react.dev's own guidance: index keys break once list items can be deleted from the middle.)

Vite's dev server proxies `/api/*` to `localhost:8000` (`frontend/vite.config.js`), so the frontend and backend run on different ports in dev with no CORS configuration needed on the backend.

### Verifying UI changes

There's no browser or Playwright installed on the host. To visually check the frontend, run Playwright inside the official Docker image with host networking, which lets the container reach the dev servers `dev.sh` started on `localhost`:

```bash
docker run --rm --network host -v "<script_dir>:/scripts" -w /scripts \
  mcr.microsoft.com/playwright/python:v1.49.0-noble \
  bash -c "pip install --quiet --break-system-packages playwright==1.49.0 && python3 script.py"
```

`--network host` only works this simply on Linux. The image bundles browser binaries but not the `playwright` pip package itself — install it at runtime, pinned to match the image tag's version (`v1.49.0-noble` → `playwright==1.49.0`).
