import tempfile
from pathlib import Path

from markers import strip_markers
from parser import parse_script
from render import render_slide
from transition_render import (
    FPS,
    render_fade_transition,
    render_file_switch_transition,
    render_lerp_rect_transition,
    render_rect_fade_transition,
    render_scroll_transition,
    render_text_diff_transition,
)
from transitions import resolve_transitions
from tts import synthesize
from video import mux_segments, render_segment

DEFAULT_HOLD_SECONDS = 1.0  # fallback hold for a slide with no voice line yet - judgment
# call, not a spec requirement, since every slide is expected to eventually have one.


def _render_transition_segment(transition, prev, slide, script_dir, path) -> None:
    if transition == "scroll_only":
        _, from_viewport, _ = strip_markers(prev.code, prev.language)
        _, to_viewport, _ = strip_markers(slide.code, slide.language)
        frames = render_scroll_transition(slide, from_viewport, to_viewport)
    elif transition == "text_diff":
        frames = render_text_diff_transition(prev, slide)
    elif transition == "file_switch":
        frames = render_file_switch_transition(prev, slide)
    elif transition == "lerp_rect":
        frames = render_lerp_rect_transition(slide, prev.rect, slide.rect, script_dir)
    elif transition == "rect_fade":
        frames = render_rect_fade_transition(slide, prev.rect, slide.rect, script_dir)
    else:  # fade
        frames = render_fade_transition(prev, slide, script_dir)

    frame_list = list(frames)
    duration = len(frame_list) / FPS
    render_segment(iter(frame_list), duration, path)


def _render_slide_segment(slide, script_dir, path, voice_base_path) -> None:
    if slide.voice.strip():
        result = synthesize(slide.voice, voice_base_path)
        duration, audio_path = result.duration, result.path
    else:
        duration = DEFAULT_HOLD_SECONDS
        audio_path = None

    frame = render_slide(slide, script_dir)
    frame_count = round(duration * FPS)
    frames = (frame for _ in range(frame_count))
    render_segment(frames, duration, path, audio_path=audio_path)


def render_script(script_path: Path, output_path: Path) -> None:
    slides = parse_script(script_path.read_text())
    script_dir = script_path.parent
    transitions = resolve_transitions(slides)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        segment_paths = []

        for i, slide in enumerate(slides):
            transition = transitions[i]
            # file_tree_change resolves but has no render function - real editors
            # don't animate the file list, so it contributes no transition segment.
            if transition is not None and transition != "file_tree_change":
                trans_path = tmp / f"segment_{len(segment_paths):04d}.mkv"
                _render_transition_segment(transition, slides[i - 1], slide, script_dir, trans_path)
                segment_paths.append(trans_path)

            slide_path = tmp / f"segment_{len(segment_paths):04d}.mkv"
            voice_base_path = tmp / f"voice_{i:04d}"
            _render_slide_segment(slide, script_dir, slide_path, voice_base_path)
            segment_paths.append(slide_path)

        mux_segments(segment_paths, output_path)
