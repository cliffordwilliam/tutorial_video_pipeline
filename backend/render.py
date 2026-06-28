import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from highlight import supported, token_color, tokenize
from markers import strip_markers
from models import CodeSlide, ImageSlide, Slide

FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

SIDEBAR_WIDTH = 380
LINE_NUMBERS_WIDTH = 85
CODE_AREA_X = SIDEBAR_WIDTH + LINE_NUMBERS_WIDTH
# One gap, used on both sides of the gutter separator (digit-to-separator and
# separator-to-code-text) - matches ttv, which reuses its own single
# CODE_GUTTER_PAD_RIGHT constant for both gaps rather than two different ones.
GUTTER_PAD = 20

# Outer margin on all four sides of the rendered editor, so it doesn't sit flush
# against the literal video frame edges - same COLOR_BACKGROUND on both sides of that
# margin (no separate "panel" color), so it reads as breathing room, not a window.
FRAME_PADDING = 48
CONTENT_WIDTH = FRAME_WIDTH - 2 * FRAME_PADDING
CONTENT_HEIGHT = FRAME_HEIGHT - 2 * FRAME_PADDING

LINE_HEIGHT = 38  # fixed, not derived from font metrics, for deterministic output
CODE_FONT_SIZE = 24  # bumped up twice now from the original 14, at the user's request -
# real-IDE-accurate sizing reads fine live but is small once compressed into a video

TREE_INDENT = CODE_FONT_SIZE + 4  # per file-tree depth level
# Gap between a row's icon (chevron for a folder, file icon for a file - exactly one of
# the two, never both, so this is the only icon-to-label gap there is) and its label.
# Deliberately a little wider than ICON_GAP's old value (8px, back when a folder row
# also drew a second icon right after the chevron) - the user asked for "uniform, and a
# tad wider than the existing file-to-icon gap" once that second icon was dropped.
ICON_GAP = 12

# Codicon glyphs (VS Code's own icon set) baked into the JetBrainsMono Nerd Font Mono
# build - same family already used for everything else here, just a patched variant
# with icon glyphs mapped into unused codepoints, so these draw via plain draw.text()
# exactly like any other character. Found by inspecting the font's cmap directly
# (fontTools) rather than trusting a remembered codepoint - PUA codepoints vary by
# icon set and font version. chevron_down (not chevron_right) since this renderer has
# no collapse state - it always shows the tree fully expanded. No folder glyph - per
# the user, the chevron alone already reads as "this is a folder", a second icon next
# to it was redundant.
ICON_CHEVRON_DOWN = ""
ICON_FILE = ""

# Catppuccin Mocha throughout - matches the syntax token colors in highlight.py, which
# were already Mocha hex values while this chrome used to be literal VS Code Dark+ hex,
# two clashing palettes in one frame. Ported from /home/clif/repositories/ttv/slides/code.py.
COLOR_BACKGROUND = "#1e1e2e"  # Base - also the sidebar's own background now (it used to
# be a distinct, darker Mantle tone, until the user asked for it to match the editor;
# the seam between the two areas is now the same kind of plain separator line the
# gutter already has, not a color difference - see the new line in _draw_file_tree).
COLOR_LINE_NUMBERS = "#7f849c"  # Overlay1 - already used in highlight.py for comments
COLOR_LINE_NUMBERS_HIGHLIGHT = "#a6adc8"  # Subtext0 - brighter, for a highlighted
# line's own number - matches ttv's CODE_GUTTER_HIGHLIGHT_COLOR exactly. The highlight
# band itself stops short of the gutter (see _draw_highlight_bands) rather than
# painting behind the number, so this is the only visual cue that row is highlighted
# once you're looking at the line-number column specifically.
COLOR_DEFAULT_TEXT = "#cdd6f4"  # Text - already used in highlight.py
COLOR_HIGHLIGHT_BG = "#313244"  # Surface0 - matches ttv's CODE_HIGHLIGHT_COLOR exactly;
# also reused below for the active-file sidebar row - the spec's color table doesn't
# define one, and reusing the "highlighted" color keeps a single consistent visual
# meaning rather than inventing an unspecified new color.
COLOR_GUTTER_BORDER = "#45475a"  # Surface1
COLOR_RECT_BORDER = "#ffff00"  # was red - perceived luminance too low to contrast
# against the dimmed background (see RECT_DIM_AMOUNT); yellow is the conventional
# spotlight/highlight choice and stays visible regardless of the image's own colors.
RECT_BORDER_WIDTH = 2
RECT_DIM_AMOUNT = 0.6  # judgment call - how much everything outside the rect darkens

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "JetBrainsMono-Regular.ttf"
ICON_FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "JetBrainsMonoNerdFontMono-Regular.ttf"
_code_font = ImageFont.truetype(str(FONT_PATH), CODE_FONT_SIZE)
# Same point size as the body text - Nerd Font icon glyphs are designed to sit inline
# with surrounding text at that text's own size, not a separately-tuned icon size.
_icon_font = ImageFont.truetype(str(ICON_FONT_PATH), CODE_FONT_SIZE)
_char_width = _code_font.getlength("M")  # true monospace: every character has this advance
# Both icon glyphs share one advance width in the Mono-patched build (that's what
# "Mono" means here - every icon is forced to a fixed cell width instead of its
# natural proportional width) - measuring once off the chevron covers all of them.
_chevron_width = _icon_font.getlength(ICON_CHEVRON_DOWN)

# draw.text()'s default anchor positions y at the font's ascender line, not centered in
# whatever row height the caller has in mind - so text drawn at a row's raw top sits
# noticeably closer to that row's top edge than its bottom (confirmed: this font's
# ascent+descent is 33px, several pixels short of LINE_HEIGHT's 38, and that slack was
# all landing below the text with nothing pushing it down to split the difference).
# Both fonts here share identical ascent/descent (same base family), so one offset
# applies everywhere text is drawn against the row grid. Row-height rectangles
# (highlight bands, the gutter separator, the sidebar fill) are NOT shifted by this -
# they mark the row's actual height, which is unaffected by where the font's baseline
# happens to sit within it.
_ascent, _descent = _code_font.getmetrics()
TEXT_Y_OFFSET = (LINE_HEIGHT - (_ascent + _descent)) / 2


def _draw_file_tree(draw: ImageDraw.ImageDraw, file_tree: list[str], active_file: str) -> None:
    # One CODE_FONT_SIZE/LINE_HEIGHT grid for the whole frame - the file tree used to
    # have its own smaller UI font and its own row-spacing formula, which (per the user)
    # made it look visibly out of place next to the code text. Each row gets a full
    # LINE_HEIGHT-tall slot, starting flush at y=0 exactly like the code's own line 1
    # does, so the sidebar's rows and the code's rows share the same rhythm top to bottom.
    # The label text itself is drawn at the row's raw top, with no extra centering
    # offset - same convention _draw_code uses - so a row here and the code line at the
    # same row index land on identical y, not just the same row height.
    #
    # Separator between the tree and the gutter, mirroring the gutter's own separator
    # between line numbers and code - now that the sidebar shares the editor's
    # background color instead of its own darker tone, this line is the only thing
    # marking that boundary at all.
    draw.line([(SIDEBAR_WIDTH, 0), (SIDEBAR_WIDTH, CONTENT_HEIGHT)], fill=COLOR_GUTTER_BORDER, width=1)

    row_top = 0
    for path in file_tree:
        is_dir = path.endswith("/")
        trimmed = path.rstrip("/")
        depth = trimmed.count("/")
        label = trimmed.rsplit("/", 1)[-1]  # no trailing "/" on folder labels either
        row_x0 = GUTTER_PAD + depth * TREE_INDENT
        # Exactly one icon per row (the chevron for a folder, the file icon for a file -
        # never both, now that the folder icon is gone) - both start at the same x and
        # share the same width, so this is the only icon-to-label gap there is, uniform
        # across every row regardless of which icon it drew.
        label_x = row_x0 + _chevron_width + ICON_GAP

        if not is_dir and trimmed == active_file.rstrip("/"):
            draw.rectangle([0, row_top, SIDEBAR_WIDTH, row_top + LINE_HEIGHT], fill=COLOR_HIGHLIGHT_BG)
            # The band above just painted over the new tree/gutter separator for this
            # row - redraw it, same fix as the code pane's own highlight band needed.
            draw.line(
                [(SIDEBAR_WIDTH, row_top), (SIDEBAR_WIDTH, row_top + LINE_HEIGHT)], fill=COLOR_GUTTER_BORDER, width=1
            )

        icon = ICON_CHEVRON_DOWN if is_dir else ICON_FILE
        draw.text((row_x0, row_top + TEXT_Y_OFFSET), icon, font=_icon_font, fill=COLOR_LINE_NUMBERS)
        draw.text((label_x, row_top + TEXT_Y_OFFSET), label, font=_code_font, fill=COLOR_DEFAULT_TEXT)
        row_top += LINE_HEIGHT


def _draw_highlight_bands(
    draw: ImageDraw.ImageDraw, highlighted_lines: set[int], viewport_top: float, start_line: int, end_line: int
) -> None:
    """Drawn before the line numbers/code text (not after, like a first attempt did) -
    its rectangle fills the full row, which would otherwise paint over and erase
    whatever was already drawn there. Starts at CODE_AREA_X, not SIDEBAR_WIDTH, though -
    unlike ttv's own full-width band, this one deliberately stops short of the gutter,
    so a highlighted line's number isn't sitting on top of a filled background; that
    line's number gets a brighter color instead (see _draw_line_numbers) as the cue."""
    for line_idx in range(start_line, end_line):
        if line_idx in highlighted_lines:
            y = (line_idx - viewport_top) * LINE_HEIGHT
            draw.rectangle([CODE_AREA_X, y, CONTENT_WIDTH, y + LINE_HEIGHT], fill=COLOR_HIGHLIGHT_BG)
            # The band above starts exactly on the gutter separator, painting over it
            # for this row - redraw it so it stays visually continuous.
            draw.line([(CODE_AREA_X, y), (CODE_AREA_X, y + LINE_HEIGHT)], fill=COLOR_GUTTER_BORDER, width=1)


def _draw_line_numbers(
    draw: ImageDraw.ImageDraw, highlighted_lines: set[int], viewport_top: float, start_line: int, end_line: int
) -> None:
    for line_idx in range(start_line, end_line):
        y = (line_idx - viewport_top) * LINE_HEIGHT
        lineno = str(line_idx + 1)
        color = COLOR_LINE_NUMBERS_HIGHLIGHT if line_idx in highlighted_lines else COLOR_LINE_NUMBERS
        # Right-aligned against the gutter separator (not a fixed left offset) - mimics
        # ttv's own gutter layout, where the digits hug the separator with a consistent
        # gap rather than sitting close to the sidebar edge regardless of digit count.
        lw = _code_font.getlength(lineno)
        draw.text((CODE_AREA_X - GUTTER_PAD - lw, y + TEXT_Y_OFFSET), lineno, font=_code_font, fill=color)


def _draw_code(
    draw: ImageDraw.ImageDraw,
    stripped_code: str,
    viewport_top: float,
    start_line: int,
    end_line: int,
    language: str,
) -> None:
    # Gutter separator - keeps the line numbers visually distinct from the code text,
    # which previously had no division at all between them.
    draw.line([(CODE_AREA_X, 0), (CODE_AREA_X, CONTENT_HEIGHT)], fill=COLOR_GUTTER_BORDER, width=1)

    # Tokenize the whole code in one pass (not line-by-line) so multi-line constructs
    # like triple-quoted strings keep correct token state across line breaks.
    line_idx = 0
    x = CODE_AREA_X + GUTTER_PAD
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
                draw.text((x, y + TEXT_Y_OFFSET), part, font=_code_font, fill=color)
            x += _char_width * len(part)
            if part_idx < len(parts) - 1:
                line_idx += 1
                x = CODE_AREA_X + GUTTER_PAD


def _draw_cursor(draw: ImageDraw.ImageDraw, line: int, col: int, viewport_top: float) -> None:
    x = CODE_AREA_X + GUTTER_PAD + col * _char_width
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
    max_visible_count = CONTENT_HEIGHT // LINE_HEIGHT
    start_line = max(0, math.floor(viewport_top))
    # +1 extra line so a partially-scrolled-in line at the bottom edge still draws;
    # Pillow clips anything actually outside the frame automatically.
    end_line = min(total_lines, start_line + max_visible_count + 1)

    # Drawn on its own CONTENT_WIDTH x CONTENT_HEIGHT sub-canvas (coordinates starting
    # at its own (0, 0), not the final frame's), then pasted in at (FRAME_PADDING,
    # FRAME_PADDING) - same reasoning as the now-removed titlebar version of this
    # function: a fractionally-scrolled line, or an overly long line of code, needs to
    # be clipped exactly at the padding boundary, and Pillow only clips for free at a
    # canvas's *real* edge, not an arbitrary internal one. No separate "fill the
    # sidebar" call needed anymore either - the whole sub-canvas already starts as
    # COLOR_BACKGROUND, which is now the sidebar's own color too.
    content = Image.new("RGB", (CONTENT_WIDTH, CONTENT_HEIGHT), COLOR_BACKGROUND)
    content_draw = ImageDraw.Draw(content)

    _draw_file_tree(content_draw, file_tree, active_file)
    _draw_highlight_bands(content_draw, highlighted_lines, viewport_top, start_line, end_line)
    _draw_line_numbers(content_draw, highlighted_lines, viewport_top, start_line, end_line)
    _draw_code(content_draw, code, viewport_top, start_line, end_line, language)
    if cursor is not None:
        _draw_cursor(content_draw, cursor[0], cursor[1], viewport_top)

    image = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), COLOR_BACKGROUND)
    image.paste(content, (FRAME_PADDING, FRAME_PADDING))
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
