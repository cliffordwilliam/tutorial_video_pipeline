import re

COMMENT_PREFIXES = {
    "python": "#",
    "py": "#",
}


class MarkerError(Exception):
    pass


def strip_markers(code: str, language: str) -> tuple[str, int, list[int]]:
    """Returns (stripped_code, viewport_top, highlighted_lines).

    viewport_top defaults to 0 if no @viewport marker is present. highlighted_lines
    are 0-based indices into the *stripped* output.
    """
    prefix = COMMENT_PREFIXES.get(language)
    if prefix is None:
        raise MarkerError(f"no known comment prefix for language {language!r}")

    viewport_marker = re.compile(rf"^\s*{re.escape(prefix)}\s*@viewport\s*$")
    highlight_suffix = re.compile(rf"\s*{re.escape(prefix)}\s*@highlight\s*$")

    output_lines: list[str] = []
    viewport_top: int | None = None
    highlighted_lines: list[int] = []

    for line in code.split("\n"):
        if viewport_marker.match(line):
            if viewport_top is not None:
                raise MarkerError("multiple @viewport markers in one slide")
            viewport_top = len(output_lines)
            continue

        match = highlight_suffix.search(line)
        if match:
            line = line[: match.start()]
            highlighted_lines.append(len(output_lines))

        output_lines.append(line)

    return "\n".join(output_lines), viewport_top if viewport_top is not None else 0, highlighted_lines
