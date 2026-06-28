from typing import Literal

from markers import strip_markers
from models import CodeSlide, ImageSlide, Slide

Transition = Literal["text_diff", "scroll_only", "file_switch", "fade", "lerp_rect"]


def resolve_transition(prev: Slide, current: Slide) -> Transition:
    if isinstance(prev, CodeSlide) and isinstance(current, CodeSlide):
        if prev.active_file != current.active_file:
            return "file_switch"
        # Compare with @viewport/@highlight markers stripped, not the raw `code`
        # string - moving just the @viewport marker to a different line changes
        # the raw text but is, per spec, still "same content, different viewport"
        # (scroll_only), not text_diff.
        prev_code, _, _ = strip_markers(prev.code, prev.language)
        current_code, _, _ = strip_markers(current.code, current.language)
        if prev_code != current_code:
            return "text_diff"
        return "scroll_only"

    if isinstance(prev, ImageSlide) and isinstance(current, ImageSlide):
        if prev.src == current.src and prev.rect != current.rect:
            return "lerp_rect"
        return "fade"

    return "fade"  # code <-> image (mixed types)


def resolve_transitions(slides: list[Slide]) -> list[Transition | None]:
    """transitions[i] is how slides[i-1] -> slides[i] should transition; transitions[0] is always None."""
    return [None] + [resolve_transition(slides[i - 1], slides[i]) for i in range(1, len(slides))]
