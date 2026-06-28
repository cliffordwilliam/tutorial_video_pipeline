# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A local-only tool for authoring and rendering programming-tutorial videos from a YAML slide script. The full intended system is described in `tutorial_video_pipeline_spec.md` at the repo root — read it for the complete feature set (the web authoring tool, Phase 2/3 items like Shiki and ElevenLabs). The web app is deliberately dumb and simple by the user's own choice: edit the YAML's fields as plain text/form inputs, click Render, wait for the blocking request to finish - no live single-frame preview (removed after initially being built), no WebSocket progress. **What's built so far**: the slide CRUD editor (`backend/` + `frontend/`), including drag-and-drop slide reordering and a canvas-based rect annotation tool for image slides (`frontend/src/ImageRectEditor.jsx` - draw the rect with the mouse over the actual image instead of typing four numbers); transition *selection* (`backend/transitions.py` — which of the four transition types applies between two slides, derived automatically, never authored); the Pillow renderer for both slide types and all four transitions (`backend/render.py`, `backend/transition_render.py`); FFmpeg segment encoding/muxing (`backend/video.py`); Piper TTS (`backend/tts.py`, no caching yet — see "Rendering pipeline" below); a whole-script render orchestrator tying all of the above into one `output.mp4` (`backend/orchestrator.py`); a `POST /api/render` endpoint and a toolbar Render button wiring the orchestrator into the web app (blocking request/response with a busy button state); a `Dockerfile` + `docker.sh` so the whole thing (ffmpeg, the Piper voice model, the built frontend, all of it) runs anywhere with just Docker installed - see "Running via Docker" below. **Not built yet**: WebSocket render progress - not planned, the blocking request is considered sufficient.

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

One-time setup for audio (Piper's voice model isn't bundled with the `piper-tts` package, and isn't committed to this repo — same reasoning as not committing `node_modules`/`.venv`):
```bash
cd backend && uv run python -m piper.download_voices en_US-lessac-low --download-dir assets/voices
```
`ffmpeg`/`ffprobe` must also be installed on the host (`apt install ffmpeg` on Ubuntu) — there's no bundled/vendored binary.

Tests: there is no automated test suite in this repo, by deliberate choice. Verify backend logic with one-off `uv run python -c "..."` snippets or `curl` against the running server. Verify the frontend visually — see "Verifying UI changes" below.

Run everything in Docker instead (no local Python/Node/ffmpeg/Piper setup needed at all):
```bash
./docker.sh [mount_dir]
```
Builds the image, runs it, polls until healthy, opens a browser, and on Ctrl+C stops + removes the container - no leftovers. See "Running via Docker" below for what this actually does and its one real limitation.

## Architecture

### YAML on disk, JSON over the wire

This is the central design decision, and the reason `backend/parser.py` exists. The on-disk script file keeps the spec's YAML format with inline `@viewport`/`@highlight` markers — chosen because it's git-diffable and hand-editable, and because moving marker positions out of the text into separate fields (e.g. a `highlighted_lines` array) would create a class of bugs where line numbers silently desync from edits. The HTTP API, however, speaks plain structured JSON, validated via Pydantic discriminated unions.

- `backend/models.py` — `CodeSlide`, `ImageSlide`, and `Slide = Annotated[Union[CodeSlide, ImageSlide], Field(discriminator="type")]`. This is the wire/validation shape.
- `backend/parser.py` — the only place that translates between the two formats: `parse_script(text) -> list[Slide]` and `serialize_script(slides) -> text`. `split_blocks()` handles splitting the script on `---`-delimited frontmatter/body pairs. `parser.py` itself never strips `@viewport`/`@highlight` — that's a render-time concern (see below), so `code` carries marker text through verbatim at this layer.

### Rendering pipeline

Each piece below was added once (and only once) something actually needed it - e.g. marker-stripping didn't exist until the renderer needed it; `render_image_frame`/`render_code_frame` (raw, marker/Rect-model-free primitives) didn't exist until transitions needed to draw at interpolated in-between positions a real `Rect`/marker-resolved slide can't express.

- `backend/markers.py` — `strip_markers(code, language) -> (stripped_code, viewport_top, highlighted_lines)`. Render-time only; never touched by `parser.py`.
- `backend/render.py` — `render_code_slide`/`render_image_slide` (take a `Slide`, resolve its markers/`Rect` internally) wrap lower-level `render_code_frame`/`render_image_frame` (fully-resolved data only - no marker stripping, rect as a raw `(x, y, w, h)` tuple instead of the strict-`int` `Rect` model). `render_slide` dispatches between the two by slide type.
- `backend/transitions.py` — `resolve_transition(prev, current)` decides which of the spec's four transition types applies, purely from slide data (never authored). File Switch resolves but has no corresponding render function - real editors cut instantly, and `render_code_slide` already highlights `active_file` in the sidebar, so an instant cut needs no animation code at all.
- `backend/transition_render.py` — one frame-sequence generator per transition type that *does* animate (`render_scroll_transition`, `render_text_diff_transition`, `render_fade_transition`, `render_lerp_rect_transition`). 60fps (not the spec's stated 30 - deliberate). Motion (scroll, lerp_rect) eases via `ease_in_out_cubic`; fades stay linear (a plain cross-dissolve); Text Diff is golden-path only (no viewport lerp - assumes the edited region stays in view).
- `backend/video.py` — `render_segment` encodes a frame sequence (+ optional real audio) to an intermediate `.mkv`; `mux_segments` concatenates segments into the final `output.mp4`. Two lessons from `/home/clif/repositories/ttv` and `/home/clif/repositories/doki-doki-coding-club` (both independently solved PTS-discontinuity/drift bugs at concat boundaries) are applied together: pad each segment's audio to exactly match its video duration, and use PCM (not AAC) for intermediate segments, encoding to AAC exactly once on the final output. **Subprocess gotcha**: writing frames to ffmpeg's stdin in a loop while also capturing stdout/stderr via `PIPE` can deadlock once progress output fills the OS pipe buffer - fixed by redirecting stderr to a temp file instead (no pipe buffer limit, no thread coordination needed).
- `backend/tts.py` — `synthesize(text, output_path) -> duration`, a thin wrapper around the `piper` CLI (stdin in, WAV out), duration read via the stdlib `wave` module. No caching yet, despite the spec's `sha256(text+model)` design - deferred deliberately, matching how both reference repos actually work in practice.
- `backend/orchestrator.py` — `render_script(script_path, output_path)` is the only piece that ties the rest of this list together: parses the script, walks `resolve_transitions()`'s output one slide at a time, renders each incoming transition (skipping File Switch - no segment) into its own temp `.mkv` via `render_segment`, then each slide's own static-frame-held + synthesized-voice segment, and finally `mux_segments()`s the whole ordered list into `output_path`. A blank `voice` line (e.g. mid-authoring, before the line is written) falls back to a fixed silent `DEFAULT_HOLD_SECONDS` hold rather than calling `synthesize` on empty text. All intermediate segment/audio files live in a `tempfile.TemporaryDirectory()`, not next to the output, since a real script produces dozens of them.

### The backend is storage-agnostic — no project/file management

`backend/main.py`'s file routes (`GET /api/file?path=...`, `POST /api/file`) take an explicit filesystem path. There is no project list, no metadata file, no database, and no "current project" concept. The filename itself (minus extension) is the slide script's title, computed client-side from `path` — never stored or sent by the backend. `POST /api/render` follows the same pattern (`{"path": ...}` in, blocks until done) but derives its own output path (`script.yaml` -> `script.mp4`, same directory) rather than taking a second explicit path - the one extra bit of convention this backend has, kept minimal on purpose (no second path input in the toolbar). `GET /api/image?path=...` (`FileResponse`) is the same explicit-path pattern again, used by `ImageRectEditor` to fetch the actual image bytes to draw on a canvas - the frontend resolves `slide.src` to an absolute path itself (`scriptDir + '/' + src`) before calling it, so the endpoint stays generic ("serve this file") rather than slide-aware.

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

### Running via Docker

`Dockerfile` is a two-stage build: an `oven/bun:1` stage builds the frontend (`bun install --frozen-lockfile && bun run build`), and the final `python:3.14-slim` stage installs `ffmpeg` via apt, installs backend deps with `uv sync` (cache-mounted, following uv's own documented Docker pattern), bakes the Piper voice model in at *build* time (`piper.download_voices`, same command as the host one-time setup above) so the image is fully self-contained with no runtime download, then copies in the built frontend. The backend serves both the API and the built frontend from one process on one port via FastAPI's `app.frontend()` (`backend/main.py`, mounted after every `/api/*` route so the API always takes priority) - this is a newer FastAPI feature purpose-built for exactly "serve a Vite/React build output with SPA fallback," found by checking the local FastAPI docs clone rather than hand-rolling a `StaticFiles` mount.

`docker.sh` mirrors the run-script pattern already used in two sibling repos (`/home/clif/repositories/pgexplore/pgexplore.sh`, `/home/clif/repositories/notebook/scripts/build.sh`): pick a free port via a Python socket trick, `docker build`, `docker run --rm` in the background, `curl -sf` poll until healthy, then `xdg-open`/`open`/print-URL as a fallback. A `trap` on `SIGINT`/`SIGTERM` stops and removes the container on Ctrl+C - combined with `--rm`, this leaves no leftover containers, images-aside, or volumes. `--user "$(id -u):$(id -g)"` runs the container as the invoking host user (not root, the image's default) specifically so rendered `.mp4` files land on the host with normal ownership instead of needing `sudo` to delete them later - caught by checking file ownership after a real render during verification, not something either reference script needed (neither writes output files back to a host bind mount).

**The one real limitation**: this app's whole architecture is built around typing arbitrary absolute host filesystem paths into the browser (`/api/file?path=...`, render output, etc - see "storage-agnostic" above). A container can't see the host filesystem unless something is bind-mounted in, and neither reference repo had to solve this (notebook has no backend file access at all; pgexplore only talks to a database). `docker.sh` resolves this by bind-mounting a host directory at the *identical* absolute path inside the container - default `$HOME`, overridable as `./docker.sh /some/other/dir` - so paths work completely unchanged from the app's perspective. Files outside the mounted directory aren't reachable from inside the container.

### Verifying changes against upstream docs

Before considering a change to this repo done, check it against locally-vendored copies of the relevant upstream framework/library docs, if any happen to be available on the machine you're working on (e.g. a cloned copy of a library's own repo). This has already caught real issues here (an unnecessary `useMemo`, an unsafe array-index React key) that plain code review missed. Not every dependency will have a local clone available - if none exists for a given library, say so explicitly rather than skipping the check silently.
