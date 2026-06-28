from pathlib import Path

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
