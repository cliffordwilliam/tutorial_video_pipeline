import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

# Default search (no path given) walks up from *this file's own location*, not
# the process's cwd - confirmed by reading dotenv's actual find_dotenv() source,
# which uses stack inspection to find the caller's __file__. So this finds
# backend/.env regardless of which directory the process happens to be launched
# from (dev.sh, the Dockerfile's WORKDIR, or direct `uv run` testing alike).
load_dotenv()

VOICE_MODEL_PATH = Path(__file__).parent / "assets" / "voices" / "en_US-lessac-low.onnx"


class SynthesisResult(NamedTuple):
    path: Path
    duration: float


def synthesize(text: str, output_path: Path) -> SynthesisResult:
    """Generates speech via TTS_BACKEND ("piper", default, or "elevenlabs"), returns
    the actual output path used (suffix decided per backend - WAV for Piper, MP3 for
    ElevenLabs) alongside its duration in seconds."""
    backend = os.environ.get("TTS_BACKEND", "piper")
    if backend == "piper":
        path = _synthesize_piper(text, output_path.with_suffix(".wav"))
    elif backend == "elevenlabs":
        path = _synthesize_elevenlabs(text, output_path.with_suffix(".mp3"))
    else:
        raise RuntimeError(f"unknown TTS_BACKEND {backend!r} (expected 'piper' or 'elevenlabs')")
    return SynthesisResult(path, _probe_duration(path))


def _synthesize_piper(text: str, output_path: Path) -> Path:
    result = subprocess.run(
        ["piper", "--model", str(VOICE_MODEL_PATH), "--output_file", str(output_path)],
        input=text,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper failed: {result.stderr}")
    return output_path


def _synthesize_elevenlabs(text: str, output_path: Path) -> Path:
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID is not set")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json", "xi-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            output_path.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"elevenlabs failed: {exc.code} {exc.read().decode()}") from exc
    return output_path


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())
