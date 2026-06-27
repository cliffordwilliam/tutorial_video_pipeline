from typing import Literal

from models import CodeSlide, ImageSlide, Slide

Transition = Literal["text_diff", "scroll_only", "file_switch", "fade", "lerp_rect"]


def resolve_transition(prev: Slide, current: Slide) -> Transition:
    if isinstance(prev, CodeSlide) and isinstance(current, CodeSlide):
        if prev.active_file != current.active_file:
            return "file_switch"
        if prev.code != current.code:
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
