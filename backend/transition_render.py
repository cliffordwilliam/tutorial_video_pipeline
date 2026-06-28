from collections.abc import Iterator

from PIL import Image

from models import CodeSlide
from render import render_code_slide

FPS = 60
SCROLL_SECONDS_PER_LINE = 0.1  # judgment call - spec says "proportional to distance", no exact rate given
MAX_SCROLL_DURATION = 1.5  # spec's stated cap


def ease_in_out_cubic(t: float) -> float:
    """Standard cubic ease-in-out - smooth acceleration then deceleration."""
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def render_scroll_transition(slide: CodeSlide, from_viewport: float, to_viewport: float) -> Iterator[Image.Image]:
    """Same slide (same active_file, same code) - only the viewport position changes."""
    distance = abs(to_viewport - from_viewport)
    duration = min(MAX_SCROLL_DURATION, distance * SCROLL_SECONDS_PER_LINE)
    frame_count = round(duration * FPS)

    for i in range(frame_count):
        t = ease_in_out_cubic(i / (frame_count - 1)) if frame_count > 1 else 1.0
        viewport_top = from_viewport + (to_viewport - from_viewport) * t
        yield render_code_slide(slide, viewport_top=viewport_top)
