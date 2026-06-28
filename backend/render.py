import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from highlight import supported, token_color, tokenize
from markers import strip_markers
from models import CodeSlide, ImageSlide, Slide

FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

SIDEBAR_WIDTH = 280
LINE_NUMBERS_WIDTH = 60
CODE_AREA_X = SIDEBAR_WIDTH + LINE_NUMBERS_WIDTH

LINE_HEIGHT = 20  # fixed, not derived from font metrics, for deterministic output
CODE_FONT_SIZE = 14
UI_FONT_SIZE = 12

COLOR_BACKGROUND = "#1e1e1e"
COLOR_SIDEBAR = "#252526"
COLOR_LINE_NUMBERS = "#858585"
COLOR_DEFAULT_TEXT = "#d4d4d4"
COLOR_HIGHLIGHT_BG = "#264f78"  # also reused below for the active-file sidebar row -
# the spec's color table doesn't define one, and reusing the "highlighted" color keeps
# a single consistent visual meaning rather than inventing an unspecified new color.
COLOR_RECT_BORDER = "#ffff00"  # was red - perceived luminance too low to contrast
# against the dimmed background (see RECT_DIM_AMOUNT); yellow is the conventional
# spotlight/highlight choice and stays visible regardless of the image's own colors.
RECT_BORDER_WIDTH = 2
RECT_DIM_AMOUNT = 0.6  # judgment call - how much everything outside the rect darkens

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "JetBrainsMono-Regular.ttf"
_code_font = ImageFont.truetype(str(FONT_PATH), CODE_FONT_SIZE)
_ui_font = ImageFont.truetype(str(FONT_PATH), UI_FONT_SIZE)
_char_width = _code_font.getlength("M")  # true monospace: every character has this advance


def _draw_file_tree(draw: ImageDraw.ImageDraw, file_tree: list[str], active_file: str) -> None:
    y = 12
    for path in file_tree:
        is_dir = path.endswith("/")
        trimmed = path.rstrip("/")
        depth = trimmed.count("/")
        label = trimmed.rsplit("/", 1)[-1] + ("/" if is_dir else "")
        x = 12 + depth * 16

        if not is_dir and trimmed == active_file.rstrip("/"):
            draw.rectangle([0, y - 2, SIDEBAR_WIDTH, y + UI_FONT_SIZE + 2], fill=COLOR_HIGHLIGHT_BG)

        draw.text((x, y), label, font=_ui_font, fill=COLOR_DEFAULT_TEXT)
        y += UI_FONT_SIZE + 8


def _draw_line_numbers(draw: ImageDraw.ImageDraw, viewport_top: float, start_line: int, end_line: int) -> None:
    for line_idx in range(start_line, end_line):
        y = (line_idx - viewport_top) * LINE_HEIGHT
        draw.text((SIDEBAR_WIDTH + 10, y), str(line_idx + 1), font=_code_font, fill=COLOR_LINE_NUMBERS)


def _draw_code(
    draw: ImageDraw.ImageDraw,
    stripped_code: str,
    highlighted_lines: set[int],
    viewport_top: float,
    start_line: int,
    end_line: int,
    language: str,
) -> None:
    for line_idx in range(start_line, end_line):
        if line_idx in highlighted_lines:
            y = (line_idx - viewport_top) * LINE_HEIGHT
            draw.rectangle([CODE_AREA_X, y, FRAME_WIDTH, y + LINE_HEIGHT], fill=COLOR_HIGHLIGHT_BG)

    # Tokenize the whole code in one pass (not line-by-line) so multi-line constructs
    # like triple-quoted strings keep correct token state across line breaks.
    line_idx = 0
    x = CODE_AREA_X + 8
    for label, text in tokenize(stripped_code, language):
        color = token_color(label)

        parts = text.split("\n")
        for part_idx, part in enumerate(parts):
            # part.strip() guards against a Pillow bug: drawing a whitespace-only
            # string at a negative y (a partially-scrolled-off line, possible now
            # that viewport_top can be fractional) raises "bad image size" inside
            # font.render - whitespace has no visible ink either way, so skip it.
            if part.strip() and start_line <= line_idx < end_line:
                y = (line_idx - viewport_top) * LINE_HEIGHT
                draw.text((x, y), part, font=_code_font, fill=color)
            x += _char_width * len(part)
            if part_idx < len(parts) - 1:
                line_idx += 1
                x = CODE_AREA_X + 8


def _draw_cursor(draw: ImageDraw.ImageDraw, line: int, col: int, viewport_top: float) -> None:
    x = CODE_AREA_X + 8 + col * _char_width
    y = (line - viewport_top) * LINE_HEIGHT
    draw.rectangle([x, y, x + 2, y + LINE_HEIGHT], fill=COLOR_DEFAULT_TEXT)


def render_code_frame(
    code: str,
    language: str,
    file_tree: list[str],
    active_file: str,
    viewport_top: float,
    highlighted_lines: set[int] = frozenset(),
    cursor: tuple[int, int] | None = None,
) -> Image.Image:
    """Draws one frame from fully-resolved data - no marker stripping, no defaults."""
    if not supported(language):
        raise ValueError(f"no lexer configured for language {language!r}")

    total_lines = code.count("\n") + 1
    max_visible_count = FRAME_HEIGHT // LINE_HEIGHT
    start_line = max(0, math.floor(viewport_top))
    # +1 extra line so a partially-scrolled-in line at the bottom edge still draws;
    # Pillow clips anything actually outside the frame automatically.
    end_line = min(total_lines, start_line + max_visible_count + 1)

    image = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, SIDEBAR_WIDTH, FRAME_HEIGHT], fill=COLOR_SIDEBAR)
    _draw_file_tree(draw, file_tree, active_file)
    _draw_line_numbers(draw, viewport_top, start_line, end_line)
    _draw_code(draw, code, highlighted_lines, viewport_top, start_line, end_line, language)
    if cursor is not None:
        _draw_cursor(draw, cursor[0], cursor[1], viewport_top)

    return image


def render_code_slide(slide: CodeSlide, viewport_top: float | None = None) -> Image.Image:
    stripped_code, default_viewport_top, highlighted = strip_markers(slide.code, slide.language)
    effective_viewport_top = default_viewport_top if viewport_top is None else viewport_top
    return render_code_frame(
        stripped_code,
        slide.language,
        slide.file_tree,
        slide.active_file,
        effective_viewport_top,
        set(highlighted),
    )


def render_image_frame(image_path: Path, rect: tuple[float, float, float, float] | None = None) -> Image.Image:
    """Draws one frame from fully-resolved data - rect as a raw (x, y, w, h) tuple,
    not a models.Rect (which has strict int fields and can't hold an interpolated
    in-between position used during the lerp_rect transition)."""
    source = Image.open(image_path)

    scale = min(FRAME_WIDTH / source.width, FRAME_HEIGHT / source.height)
    scaled_size = (round(source.width * scale), round(source.height * scale))
    resized = source.resize(scaled_size).convert("RGBA")

    offset_x = (FRAME_WIDTH - scaled_size[0]) // 2
    offset_y = (FRAME_HEIGHT - scaled_size[1]) // 2

    # Always go through alpha_composite (not paste-with-self-as-mask) per Pillow's
    # own docs recommendation for combining images with respect to alpha channels -
    # converting every source to RGBA uniformly means opaque sources (no real
    # transparency) and ones with a real alpha channel both go through one path.
    background = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), COLOR_BACKGROUND)
    layer = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
    layer.paste(resized, (offset_x, offset_y))
    frame = Image.alpha_composite(background, layer).convert("RGB")

    if rect is not None:
        x, y, w, h = rect
        x0 = offset_x + x * scale
        y0 = offset_y + y * scale
        x1 = offset_x + (x + w) * scale
        y1 = offset_y + (y + h) * scale

        # Dim everything outside the rect to draw the eye to its contents - paste the
        # original, undimmed crop of just the rect region back on top of a darkened
        # copy of the whole frame. crop()/paste() need integer coordinates, unlike
        # draw.rectangle() below, which already tolerates floats.
        crop_box = (round(x0), round(y0), round(x1), round(y1))
        dimmed = Image.blend(frame, Image.new("RGB", frame.size, (0, 0, 0)), RECT_DIM_AMOUNT)
        dimmed.paste(frame.crop(crop_box), crop_box)
        frame = dimmed

        draw = ImageDraw.Draw(frame)
        draw.rectangle([x0, y0, x1, y1], outline=COLOR_RECT_BORDER, width=RECT_BORDER_WIDTH)

    return frame


def render_image_slide(slide: ImageSlide, script_dir: Path) -> Image.Image:
    rect = (slide.rect.x, slide.rect.y, slide.rect.w, slide.rect.h) if slide.rect else None
    return render_image_frame(script_dir / slide.src, rect)


def render_slide(slide: Slide, script_dir: Path) -> Image.Image:
    return render_code_slide(slide) if isinstance(slide, CodeSlide) else render_image_slide(slide, script_dir)
