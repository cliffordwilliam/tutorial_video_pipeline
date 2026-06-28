from collections.abc import Iterator
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from markers import strip_markers
from models import CodeSlide, ImageSlide, Rect, Slide
from render import FRAME_HEIGHT, FRAME_WIDTH, render_code_frame, render_code_slide, render_image_frame, render_slide

FPS = 60
SCROLL_SECONDS_PER_LINE = 0.1  # judgment call - spec says "proportional to distance", no exact rate given
MAX_SCROLL_DURATION = 1.5  # spec's stated cap
CHARS_PER_SECOND = 80  # spec's stated default; "configurable" is explicitly Phase 3, not now
CURSOR_BLINK_SECONDS = 0.25
FADE_SECONDS = 0.3  # spec's exact number, both phases
LERP_RECT_SECONDS = 0.5  # spec's exact number
FILE_SWITCH_SECONDS = 0.3  # quick UI cross-fade, not a scene transition
RECT_FADE_SECONDS = 0.3


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


def render_file_switch_transition(prev: CodeSlide, current: CodeSlide) -> Iterator[Image.Image]:
    """The code pane cuts instantly to current's content (real editors don't animate
    this); only the sidebar's highlighted row cross-fades from prev.active_file to
    current.active_file. Both blended frames use current's own code/file_tree/viewport
    and differ only in which file is passed as active_file, so blending them only
    visibly affects the highlight band - no special-cased drawing needed. If
    prev.active_file isn't even in current.file_tree (e.g. renamed away), the first
    frame simply has nothing highlighted, degrading to a clean fade-in."""
    current_code, viewport_top, highlighted = strip_markers(current.code, current.language)
    frame_old_highlight = render_code_frame(
        current_code, current.language, current.file_tree, prev.active_file, viewport_top, set(highlighted)
    )
    frame_new_highlight = render_code_frame(
        current_code, current.language, current.file_tree, current.active_file, viewport_top, set(highlighted)
    )
    frame_count = round(FILE_SWITCH_SECONDS * FPS)

    for i in range(frame_count):
        t = i / (frame_count - 1) if frame_count > 1 else 1.0
        yield Image.blend(frame_old_highlight, frame_new_highlight, t)


def _diff_steps(prev: str, current: str) -> list[tuple[str, int]]:
    """One entry per character edit: backspaces deleted/replaced segments from
    their right edge, then types inserted/replaced segments left to right."""
    # autojunk's "popular elements are junk" heuristic is meant for line-level diffing
    # of text files (excluding boilerplate-like blank/repeated lines); for character-
    # level diffing of code, repeated whitespace/indentation is meaningful and
    # shouldn't be excluded from matching, so it's disabled here.
    matcher = SequenceMatcher(None, prev, current, autojunk=False)
    state = list(prev)
    pos = 0
    steps: list[tuple[str, int]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            pos += i2 - i1
            continue

        if tag in ("delete", "replace"):
            cursor = pos + (i2 - i1)
            for _ in range(i2 - i1):
                cursor -= 1
                del state[cursor]
                steps.append(("".join(state), cursor))

        if tag in ("insert", "replace"):
            for k in range(j2 - j1):
                state.insert(pos + k, current[j1 + k])
                steps.append(("".join(state), pos + k + 1))
            pos += j2 - j1

    return steps


def _offset_to_line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset)
    col = offset - text.rfind("\n", 0, offset) - 1
    return line, col


def render_text_diff_transition(prev: CodeSlide, current: CodeSlide) -> Iterator[Image.Image]:
    """Golden path only: assumes the edited region stays in view throughout, so the
    viewport is fixed (current's own declared position) - no scroll-while-diffing."""
    prev_code, _, _ = strip_markers(prev.code, prev.language)
    current_code, viewport_top, _ = strip_markers(current.code, current.language)

    steps = _diff_steps(prev_code, current_code)
    # Bookend with the cursor-less, fully-settled start/end states so this transition
    # hands off cleanly to and from the plain (no-cursor) frames rendered for the
    # slides themselves - duration is still driven by the number of actual edits.
    states: list[tuple[str, int | None]] = [(prev_code, None), *steps, (current_code, None)]
    duration = len(steps) / CHARS_PER_SECOND
    frame_count = round(duration * FPS)
    blink_frames = max(1, round(CURSOR_BLINK_SECONDS * FPS))

    for i in range(frame_count):
        t = i / (frame_count - 1) if frame_count > 1 else 1.0
        state_idx = round(t * (len(states) - 1))
        code, cursor_offset = states[state_idx]
        cursor = _offset_to_line_col(code, cursor_offset) if cursor_offset is not None else None
        cursor_visible = cursor is not None and (i // blink_frames) % 2 == 0

        yield render_code_frame(
            code,
            current.language,
            current.file_tree,
            current.active_file,
            viewport_top,
            cursor=cursor if cursor_visible else None,
        )


def render_fade_transition(prev: Slide, current: Slide, script_dir: Path) -> Iterator[Image.Image]:
    """prev's frame fades to black, then black fades to current's frame. Works for
    image<->image (different src) and any mixed code<->image pair."""
    prev_frame = render_slide(prev, script_dir)
    current_frame = render_slide(current, script_dir)
    black = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0))
    frame_count = round(FADE_SECONDS * FPS)

    for i in range(frame_count):
        alpha = i / (frame_count - 1) if frame_count > 1 else 1.0
        yield Image.blend(prev_frame, black, alpha)

    for i in range(frame_count):
        alpha = i / (frame_count - 1) if frame_count > 1 else 1.0
        yield Image.blend(black, current_frame, alpha)


def render_lerp_rect_transition(
    slide: ImageSlide, from_rect: Rect, to_rect: Rect, script_dir: Path
) -> Iterator[Image.Image]:
    """Same image (same src), both rects already set and different - only the rect's
    position/size animates. A rect appearing/disappearing (one side None) is a
    separate case, resolved to rect_fade instead - see render_rect_fade_transition."""
    image_path = script_dir / slide.src
    frame_count = round(LERP_RECT_SECONDS * FPS)

    for i in range(frame_count):
        t = ease_in_out_cubic(i / (frame_count - 1)) if frame_count > 1 else 1.0
        rect = (
            from_rect.x + (to_rect.x - from_rect.x) * t,
            from_rect.y + (to_rect.y - from_rect.y) * t,
            from_rect.w + (to_rect.w - from_rect.w) * t,
            from_rect.h + (to_rect.h - from_rect.h) * t,
        )
        yield render_image_frame(image_path, rect)


def render_rect_fade_transition(
    slide: ImageSlide, from_rect: Rect | None, to_rect: Rect | None, script_dir: Path
) -> Iterator[Image.Image]:
    """Same image, a rect appearing (to_rect set, from_rect None) or disappearing
    (the reverse) - exactly one is None, resolved by transitions.py. The rect's
    position/size is fixed throughout; only its visibility fades. Linear alpha, not
    eased - matches the rule that fades stay linear while positional motion eases."""
    image_path = script_dir / slide.src
    rect = to_rect or from_rect
    frame_without = render_image_frame(image_path, rect=None)
    frame_with = render_image_frame(image_path, rect=(rect.x, rect.y, rect.w, rect.h))
    frame_count = round(RECT_FADE_SECONDS * FPS)

    for i in range(frame_count):
        alpha = i / (frame_count - 1) if frame_count > 1 else 1.0
        start, end = (frame_without, frame_with) if to_rect else (frame_with, frame_without)
        yield Image.blend(start, end, alpha)
