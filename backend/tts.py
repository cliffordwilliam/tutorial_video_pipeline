import subprocess
import wave
from pathlib import Path

VOICE_MODEL_PATH = Path(__file__).parent / "assets" / "voices" / "en_US-lessac-low.onnx"


def synthesize(text: str, output_path: Path) -> float:
    """Generates speech via Piper, returns the resulting audio duration in seconds."""
    result = subprocess.run(
        ["piper", "--model", str(VOICE_MODEL_PATH), "--output_file", str(output_path)],
        input=text,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper failed: {result.stderr}")

    with wave.open(str(output_path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()
