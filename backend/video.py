import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from PIL import Image

from render import FRAME_HEIGHT, FRAME_WIDTH
from transition_render import FPS

AUDIO_SAMPLE_RATE = 48000


def render_segment(
    frames: Iterator[Image.Image],
    duration: float,
    output_path: Path,
    audio_path: Path | None = None,
) -> None:
    """Encodes a frame sequence (+ optional real audio) into one intermediate
    segment - PCM audio padded to exactly `duration` (ttv's fix for PTS
    discontinuities from mismatched audio/video segment lengths). `output_path`
    must end in `.mkv` - MP4 containers don't support PCM audio.

    Caller's contract: the frame iterator must yield exactly round(duration * FPS)
    frames - ffmpeg's own `-t duration` and the piped frame count must agree on
    the video side, or one silently truncates the other.
    """
    video_args = [
        "-f", "rawvideo",
        "-pixel_format", "rgb24",
        "-video_size", f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
        "-framerate", str(FPS),
        "-i", "-",
    ]

    if audio_path is not None:
        audio_args = ["-i", str(audio_path), "-af", f"apad=whole_dur={duration:.3f}", "-t", f"{duration:.3f}"]
    else:
        audio_args = ["-f", "lavfi", "-i", f"anullsrc=r={AUDIO_SAMPLE_RATE}:cl=mono", "-t", f"{duration:.3f}"]

    cmd = [
        "ffmpeg", "-y",
        *video_args,
        *audio_args,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-ar", str(AUDIO_SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le",
        str(output_path),
    ]

    # stderr goes to a temp *file*, not a pipe: writing stdin in a loop while also
    # capturing stderr via PIPE can deadlock once ffmpeg's progress output fills
    # the OS pipe buffer (Python's subprocess docs warn about exactly this) -
    # small test segments never hit it, but any real-length video would. A file
    # has no such buffer limit, so no second thread/communicate() coordination
    # is needed at all.
    with tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr_file)
        for frame in frames:
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        process.wait()

        if process.returncode != 0:
            stderr_file.seek(0)
            raise RuntimeError(f"ffmpeg failed encoding segment {output_path}:\n{stderr_file.read().decode()}")


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(["ffmpeg", "-y", *args], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")


def mux_segments(segment_paths: list[Path], output_path: Path) -> None:
    """Concatenates frame-aligned PCM segments via the concat demuxer (-c copy,
    doki-doki-coding-club's fix for PCM's lack of encoder delay/edit-list breaking
    concat boundaries), then encodes audio to AAC exactly once for the final
    output.mp4."""
    list_path = output_path.parent / f"{output_path.stem}_concat_list.txt"
    concat_path = output_path.parent / f"{output_path.stem}_concat.mkv"

    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths))

    try:
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(concat_path)])
        _run_ffmpeg(["-i", str(concat_path), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(output_path)])
    finally:
        list_path.unlink(missing_ok=True)
        concat_path.unlink(missing_ok=True)
