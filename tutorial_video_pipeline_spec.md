# Tutorial Video Pipeline — Spec

## Overview

A self-contained pipeline for authoring and rendering programming tutorial videos. The author writes a YAML script describing slides, transitions, and voicelines. A local web app (browser + FastAPI backend) handles authoring, preview, and final video export. The renderer is deterministic — same input always produces the same output.

The visual style mimics a VS Code-like editor: dark background, file tree, line numbers, syntax-highlighted code. Content is stateless — continuity between slides (active file, scroll position, visible code) is fully declared in the script by the author.

---

## Input Format — YAML Frontmatter Blocks

Each slide is a YAML frontmatter block followed by optional plain text content. Slides are separated by `---`. The full script lives in a single `.yaml` file.

### Code Slide

```yaml
---
type: code
voice: "Here we define the parse function"
language: python
active_file: parser.py
file_tree:
  - src/
  - src/main.py
  - src/parser.py
---
def parse(tokens):
    result = []
# @viewport
    for token in tokens:
        result.append(token)  # @highlight
    return result
```

### Image Slide

```yaml
---
type: image
voice: "Notice the memory layout shown here"
src: diagram.png
rect:
  x: 120
  y: 80
  w: 300
  h: 150
transition: lerp_rect
---
```

### Fields Reference

| Field | Required | Description |
|---|---|---|
| `type` | yes | `code` or `image` |
| `voice` | yes | Voiceline text spoken after transition completes |
| `language` | code only | Language for syntax highlighting (e.g. `python`, `js`) |
| `active_file` | code only | Filename highlighted in the file tree |
| `file_tree` | code only | List of paths shown in sidebar. Dirs end with `/` |
| `src` | image only | Path to image file relative to project dir |
| `rect` | image only | Axis-aligned annotation rectangle `{x, y, w, h}` in pixels |
| `transition` | image only | `fade` (default) or `lerp_rect` |

### Inline Body Markers

Markers are placed inline in the code body and stripped before rendering. The comment prefix is determined by the `language` field.

| Marker | Placement | Effect |
|---|---|---|
| `# @viewport` | Its own line | Viewport top is set to this line. Line is removed from output. |
| `# @highlight` | End of a code line | That line gets a subtle background highlight. Marker is stripped. |

Example with both markers (Python):

```python
def parse(tokens):
    result = []
# @viewport
    for token in tokens:
        result.append(token)  # @highlight
        result.append(token2) # @highlight
    return result
```

For other languages the prefix changes: `// @viewport`, `// @highlight` for JS/C/etc. The parser determines the prefix from `language`.

---

## Transition System

Every slide follows this sequence:

```
1. Transition animation plays to completion
2. Voiceline audio plays to completion
3. Next slide begins
```

There are four transition types:

### 1. Text Diff (code → code, content changed)

- Compute character-level diff between previous slide content and current slide content using `difflib.SequenceMatcher`
- Animate a blinking cursor deleting and inserting characters to transform old content into new
- Speed: configurable characters per second (default 80 cps)
- Viewport lerps simultaneously if `@viewport` position changed

### 2. Scroll Only (code → code, same content, different `@viewport`)

- No diff animation
- Viewport Y offset lerps smoothly from old position to new
- Duration: proportional to scroll distance, capped at 1.5s

### 3. File Switch (code → code, different `active_file`)

- Quick fade to black (0.2s) then fade in new file content
- If content also changed, diff animation plays after fade in

### 4. Image Transition

- `fade`: fade out to black (0.3s), swap image, fade in (0.3s)
- `lerp_rect`: if same image with different rect, lerp the rectangle position and size over 0.5s. No fade.

---

## Renderer — Visual Layout

The renderer uses **Pillow** to draw frames at 1920×1080. The layout mimics VS Code dark theme.

```
┌───────────┬──────┬──────────────────────────┐
│           │ Line │                          │
│ File tree │  nos │  Code area               │
│           │      │  (syntax highlighted)    │
│           │      │                          │
└───────────┴──────┴──────────────────────────┘
```

### Color Scheme (VS Code Dark+ approximate)

| Element | Color |
|---|---|
| Background | `#1e1e1e` |
| Sidebar | `#252526` |
| Line numbers | `#858585` |
| Default text | `#d4d4d4` |
| Highlight line bg | `#264f78` |
| Annotation rect | `#ff0000` (2px border) |

### Syntax Highlighting

- **Phase 1**: Pygments with a VS Code Dark+ approximation theme
- **Phase 2**: Shiki via a small Node sidecar script (`shiki_highlight.js`) called via subprocess. Takes `{code, language}` on stdin, returns token list on stdout. FastAPI caches results by `sha256(code + language)`.

### Font

JetBrains Mono or Fira Code, loaded from a bundled TTF. Fixed at 14px for code, 12px for UI elements. This ensures consistent frame dimensions across platforms.

---

## Audio — Piper TTS

- **Engine**: Piper (local, offline)
- **Phase 2**: ElevenLabs API (drop-in replacement, same interface)
- **Cache key**: `sha256(voice_text + model_name)` → stored as `cache/audio/<hash>.wav`
- On render, cache is checked before invoking Piper. Cache is shared between preview and final render so audio is never generated twice.

---

## Video Rendering Pipeline

```
YAML script
    │
    ▼
Parse slides → strip & resolve inline markers → resolve transitions → compute frame sequences
    │
    ▼
For each slide:
  - Render frames (Pillow) → silent video segment (imageio / OpenCV)
  - Resolve audio from cache or generate via Piper
    │
    ▼
FFmpeg: concatenate segments + mux audio tracks with correct offsets
    │
    ▼
output.mp4 (H.264, AAC)
```

Frame rate: 30fps. Each transition segment renders exactly as many frames as its duration requires.

---

## Web App — Authoring Tool

### Backend: FastAPI

Endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/project` | Load current YAML script |
| `POST` | `/project` | Save YAML script to disk |
| `POST` | `/preview/audio` | Generate or return cached audio for a voice line |
| `POST` | `/preview/frame` | Render a single frame for a slide (for visual preview) |
| `POST` | `/render` | Start full video render job |
| `GET` | `/render/status` | WebSocket — stream render progress |
| `GET` | `/images/{filename}` | Serve project image files |

### Frontend: React

**Slide List Panel** — ordered list of slides. Click to select and edit.

**Editor Panel** — YAML fields as form inputs:
- Dropdowns for `type`, `language`, `transition`
- Text inputs for `active_file`, `voice`
- Multiline text area for code content (with `@viewport` and `@highlight` markers authored inline)
- File tree editor (add/remove paths)

**Image Annotation Tool** — for image slides:
- Displays the image
- Canvas overlay for drawing the rect: mouse drag sets `x, y, w, h`
- Rect values shown as numeric inputs (editable directly)
- Red rect preview drawn on canvas

**Preview Panel**:
- Text diff animation rendered in-browser with JS (no backend call needed)
- Scroll lerp previewed in-browser
- Play button calls `/preview/audio` and plays the WAV
- Single frame render calls `/preview/frame` and displays result image

**Render Button** — calls `/render`, opens a progress panel fed by WebSocket showing per-slide progress.

---

## Project Structure on Disk

```
my_project/
  script.yaml          # The authored slide script
  images/              # Source images referenced by slides
  cache/
    audio/             # Piper WAV cache (keyed by hash)
    highlight/         # Shiki token cache (keyed by hash)
  output/
    output.mp4         # Final rendered video
    segments/          # Intermediate per-slide video segments
```

---

## Implementation Phases

### Phase 1 — Core Pipeline
- YAML parser and slide model
- Inline marker parser: strip `@viewport` and `@highlight`, record positions
- Pillow renderer: layout, font, line numbers, file tree, highlight line bg
- Pygments syntax highlighting
- Text diff transition (cursor animation)
- Scroll lerp transition
- File switch transition (fade)
- Image slide with rect annotation
- Image fade and lerp_rect transitions
- Piper TTS integration with hash cache
- FFmpeg mux

### Phase 2 — Web Authoring Tool
- FastAPI backend with all endpoints
- React frontend: slide list, editor panel, preview panel
- Canvas-based rect annotation tool
- In-browser diff animation preview
- WebSocket render progress

### Phase 3 — Quality
- Shiki sidecar for VS Code-accurate syntax highlighting
- ElevenLabs API as drop-in TTS replacement
- Configurable typing speed per slide
- Configurable transition durations

---

## Key Design Decisions

**Stateless renderer** — the renderer has no memory between slides. All state (active file, file tree, scroll position, code content) is declared explicitly in each slide's YAML. Continuity is the author's responsibility, not the renderer's. This keeps the renderer simple and the output fully reproducible.

**Inline markers over frontmatter fields** — `@viewport` and `@highlight` live in the code body where they describe, not in the frontmatter. This eliminates line-counting errors and makes the script self-documenting.

**No tab bar** — one file is shown at a time. The file tree sidebar provides enough project context. Removing tabs simplifies the renderer and the schema.

**Single source of truth** — the YAML file is the only thing that matters. The web tool reads and writes it. The renderer reads it. You can hand-edit it, diff it in git, and review it with an AI.

**Transition then voice** — every slide follows the same rule: transition animation completes fully, then voiceline plays. No overlap. Simple to reason about and author.

**Cache everything deterministic** — audio and syntax highlighting are expensive and deterministic. Both are cached by content hash and reused across preview and final render.