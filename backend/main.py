from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class SaveRequest(BaseModel):
    path: str
    content: str


@app.get("/api/file")
def read_file(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    file_path = Path(path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    return {"content": file_path.read_text()}


@app.post("/api/file")
def write_file(req: SaveRequest):
    if not req.path:
        raise HTTPException(status_code=400, detail="path is required")

    file_path = Path(req.path)
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(req.content)

    return {"ok": True}
