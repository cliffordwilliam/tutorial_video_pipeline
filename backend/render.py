import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.style import Style
from pygments.token import Token

from markers import strip_markers
from models import CodeSlide

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

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "JetBrainsMono-Regular.ttf"
_code_font = ImageFont.truetype(str(FONT_PATH), CODE_FONT_SIZE)
_ui_font = ImageFont.truetype(str(FONT_PATH), UI_FONT_SIZE)
_char_width = _code_font.getlength("M")  # true monospace: every character has this advance

LEXERS = {
    "python": PythonLexer(),
    "py": PythonLexer(),
}


class VSCodeDarkPlusStyle(Style):
    # Pillow only has the Regular weight loaded, so no bold/italic modifiers here -
    # they'd be silently ignored anyway without a matching font variant.
    styles = {
        Token.Keyword: "#569cd6",
        Token.Keyword.Constant: "#569cd6",
        Token.Keyword.Declaration: "#569cd6",
        Token.Name.Function: "#dcdcaa",
        Token.Name.Class: "#4ec9b0",
        Token.Name.Builtin: "#569cd6",
        Token.String: "#ce9178",
        Token.Comment: "#6a9955",
        Token.Number: "#b5cea8",
        Token.Operator: COLOR_DEFAULT_TEXT,
        Token.Punctuation: COLOR_DEFAULT_TEXT,
        Token.Text: COLOR_DEFAULT_TEXT,
    }


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

    # Lex the whole code in one pass (not line-by-line) so multi-line constructs
    # like triple-quoted strings keep correct token state across line breaks.
    line_idx = 0
    x = CODE_AREA_X + 8
    for token_type, text in lex(stripped_code, LEXERS[language]):
        color_hex = VSCodeDarkPlusStyle.style_for_token(token_type)["color"]
        color = f"#{color_hex}" if color_hex else COLOR_DEFAULT_TEXT

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


def render_code_slide(slide: CodeSlide, viewport_top: float | None = None) -> Image.Image:
    if slide.language not in LEXERS:
        raise ValueError(f"no lexer configured for language {slide.language!r}")

    stripped_code, default_viewport_top, highlighted = strip_markers(slide.code, slide.language)
    effective_viewport_top = default_viewport_top if viewport_top is None else viewport_top
    highlighted_set = set(highlighted)
    total_lines = stripped_code.count("\n") + 1

    max_visible_count = FRAME_HEIGHT // LINE_HEIGHT
    start_line = max(0, math.floor(effective_viewport_top))
    # +1 extra line so a partially-scrolled-in line at the bottom edge still draws;
    # Pillow clips anything actually outside the frame automatically.
    end_line = min(total_lines, start_line + max_visible_count + 1)

    image = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, SIDEBAR_WIDTH, FRAME_HEIGHT], fill=COLOR_SIDEBAR)
    _draw_file_tree(draw, slide.file_tree, slide.active_file)
    _draw_line_numbers(draw, effective_viewport_top, start_line, end_line)
    _draw_code(draw, stripped_code, highlighted_set, effective_viewport_top, start_line, end_line, slide.language)

    return image
