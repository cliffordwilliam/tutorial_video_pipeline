import re

import yaml
from pydantic import TypeAdapter, ValidationError

from models import CodeSlide, ImageSlide, Slide

_DELIMITER = re.compile(r"^---\s*$", re.MULTILINE)
_SLIDE_ADAPTER: TypeAdapter[Slide] = TypeAdapter(Slide)


class ScriptParseError(Exception):
    pass


class _IndentingDumper(yaml.SafeDumper):
    """Indents list items under their key, matching the spec's examples
    (PyYAML's default aligns them with the key instead)."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def split_blocks(text: str) -> list[tuple[str, str]]:
    segments = _DELIMITER.split(text)

    if segments[0].strip():
        raise ScriptParseError("content found before the first '---' delimiter")

    segments = segments[1:]
    if len(segments) % 2 != 0:
        raise ScriptParseError(
            "unmatched '---' delimiter - each slide needs an opening and closing delimiter"
        )

    return [(segments[i], segments[i + 1]) for i in range(0, len(segments), 2)]


def parse_script(text: str) -> list[Slide]:
    slides: list[Slide] = []

    for i, (frontmatter_text, body_text) in enumerate(split_blocks(text)):
        try:
            data = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise ScriptParseError(f"slide {i}: invalid YAML - {e}") from e

        if not isinstance(data, dict):
            raise ScriptParseError(f"slide {i}: frontmatter must be a YAML mapping")

        if data.get("type") == "code":
            data["code"] = body_text.strip("\n")
        elif body_text.strip():
            raise ScriptParseError(f"slide {i}: image slides cannot have body content")

        try:
            slides.append(_SLIDE_ADAPTER.validate_python(data))
        except ValidationError as e:
            raise ScriptParseError(f"slide {i}: {e}") from e

    return slides


def serialize_script(slides: list[Slide]) -> str:
    parts = []

    for slide in slides:
        if isinstance(slide, CodeSlide):
            frontmatter = slide.model_dump(exclude={"code"})
            body = slide.code
        elif isinstance(slide, ImageSlide):
            frontmatter = slide.model_dump()
            body = ""
        else:
            raise ScriptParseError(f"unknown slide type: {type(slide)!r}")

        yaml_text = yaml.dump(
            frontmatter, Dumper=_IndentingDumper, sort_keys=False, default_flow_style=False
        )
        parts.append(f"---\n{yaml_text}---\n{body}")

    return "\n".join(parts) + ("\n" if parts else "")
