import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from markers import MarkerError
from models import Slide
from orchestrator import render_script
from parser import ScriptParseError, parse_script, serialize_script

app = FastAPI()


class SlidesResponse(BaseModel):
    slides: list[Slide]


class SaveRequest(BaseModel):
    path: str
    slides: list[Slide]


class RenderRequest(BaseModel):
    path: str


class TtsBackendRequest(BaseModel):
    backend: Literal["piper", "elevenlabs"]


class BrowseEntry(BaseModel):
    name: str
    type: Literal["dir", "file"]


class BrowseResponse(BaseModel):
    path: str
    entries: list[BrowseEntry]


@app.get("/api/file", response_model=SlidesResponse)
def read_file(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    file_path = Path(path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    try:
        slides = parse_script(file_path.read_text())
    except ScriptParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"slides": slides}


@app.post("/api/file")
def write_file(req: SaveRequest):
    if not req.path:
        raise HTTPException(status_code=400, detail="path is required")

    file_path = Path(req.path)
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(serialize_script(req.slides))

    return {"ok": True}


@app.get("/api/image")
def read_image(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    return FileResponse(file_path)


@app.get("/api/browse", response_model=BrowseResponse)
def browse(path: str | None = None, extensions: str | None = None):
    dir_path = Path(path) if path else Path.home()
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    ext_filter = {e.strip().lower().lstrip(".") for e in (extensions or "").split(",") if e.strip()}

    entries = []
    try:
        for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    entries.append({"name": entry.name, "type": "dir"})
                elif not ext_filter or entry.suffix.lower().lstrip(".") in ext_filter:
                    entries.append({"name": entry.name, "type": "file"})
            except OSError:
                continue  # broken symlink etc - skip rather than fail the whole listing
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"path": str(dir_path), "entries": entries}


@app.get("/api/tts-status")
def tts_status():
    backend = os.environ.get("TTS_BACKEND", "piper")
    if backend == "elevenlabs":
        configured = bool(os.environ.get("ELEVENLABS_API_KEY")) and bool(os.environ.get("ELEVENLABS_VOICE_ID"))
        return {"backend": "elevenlabs", "configured": configured}
    return {"backend": "piper", "configured": True}


@app.post("/api/tts-backend")
def set_tts_backend(req: TtsBackendRequest):
    # In-memory only - flips which branch synthesize() takes on its next call. Never
    # touches backend/.env or re-runs load_dotenv(), so credentials still only ever
    # enter the process at startup; switching to "elevenlabs" without a configured key
    # is allowed here and simply fails at render time, same as it does today.
    os.environ["TTS_BACKEND"] = req.backend
    return tts_status()


@app.post("/api/render")
def render(req: RenderRequest):
    if not req.path:
        raise HTTPException(status_code=400, detail="path is required")

    script_path = Path(req.path)
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    output_path = script_path.with_suffix(".mp4")
    try:
        render_script(script_path, output_path)
    except (ScriptParseError, MarkerError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:  # ffmpeg/piper subprocess failures
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"ok": True, "output_path": str(output_path)}


# Serves the Vite build output baked into the Docker image (see Dockerfile) -
# checked only after the routes above, so the API is unaffected. check_dir=False
# because frontend_dist doesn't exist in plain local dev (Vite's own dev server
# handles that case instead - see dev.sh).
FRONTEND_DIST = Path(__file__).parent.parent / "frontend_dist"
app.frontend("/", directory=str(FRONTEND_DIST), check_dir=False)
