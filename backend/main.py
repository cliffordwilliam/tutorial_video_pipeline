import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from markers import MarkerError
from models import CodeSlide, Slide
from parser import ScriptParseError, parse_script, serialize_script
from render import render_code_slide

app = FastAPI()


class SlidesResponse(BaseModel):
    slides: list[Slide]


class SaveRequest(BaseModel):
    path: str
    slides: list[Slide]


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


@app.post("/api/preview/frame")
def preview_frame(slide: Slide):
    if not isinstance(slide, CodeSlide):
        raise HTTPException(status_code=400, detail="frame preview is only implemented for code slides so far")

    try:
        image = render_code_slide(slide)
    except (MarkerError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
