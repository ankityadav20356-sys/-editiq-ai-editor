"""Deterministic Phase 1 planning rules.

Each function takes a normalized+segmented Transcript (and a
PlannerConfig) and returns a list of operation dicts matching the
edit_plan schema's per-type required fields (see
schemas/edit_plan_validate.py's _OPERATION_SPECS). No rule here downloads
or fetches any asset -- b-roll rules only ever produce a search query.
"""

from __future__ import annotations

from .models import PlannerConfig


def generate_captions(transcript, config: PlannerConfig = None):
    """One caption operation per transcript segment."""

    ops = []
    for seg in transcript.segments:
        if not seg.text.strip():
            continue
        ops.append({
            "type": "caption",
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "word_level_timing": bool(seg.words),
        })
    return ops


def generate_emphasis(transcript, config: PlannerConfig = None):
    """Pick at most N emphasis candidates per segment: long words or keyword hits."""

    config = config or PlannerConfig()
    ops = []
    for seg in transcript.segments:
        picked = 0
        for w in seg.words:
            if picked >= config.max_emphasis_per_segment:
                break
            bare = w.text.strip(".,!?;:").lower()
            is_keyword = bare in config.emphasis_keywords
            is_long = len(bare) >= config.emphasis_min_word_len
            if is_keyword or is_long:
                ops.append({
                    "type": "emphasis",
                    "start": w.start,
                    "end": w.end,
                    "word": w.text,
                    "reason": "keyword" if is_keyword else "long_word",
                })
                picked += 1
    return ops


def generate_zooms(transcript, config: PlannerConfig = None, emphasis_ops=None):
    """Restrained punch-in zoom around each emphasis point (not constant zooming)."""

    config = config or PlannerConfig()
    if emphasis_ops is None:
        emphasis_ops = generate_emphasis(transcript, config)

    ops = []
    for e in emphasis_ops:
        start = max(0.0, e["start"] - config.zoom_pad_s)
        end = e["end"] + config.zoom_pad_s
        ops.append({
            "type": "zoom",
            "start": round(start, 3),
            "end": round(end, 3),
            "scale": config.zoom_scale,
        })
    return ops


def generate_broll_suggestions(transcript, config: PlannerConfig = None):
    """Keyword-triggered b-roll SUGGESTIONS (search concepts only, never downloads)."""

    config = config or PlannerConfig()
    ops = []
    seen_windows = []  # avoid stacking many overlapping broll hits in one segment
    for seg in transcript.segments:
        lower = seg.text.lower()
        for keyword, query in config.broll_keywords.items():
            if keyword in lower:
                ops.append({
                    "type": "broll",
                    "start": seg.start,
                    "end": seg.end,
                    "query": query,
                    "reason": f"keyword match: '{keyword}'",
                })
                break  # one b-roll suggestion per segment is enough for Phase 1
    return ops


def generate_silence_cuts(transcript, config: PlannerConfig = None):
    """Suggest cuts for gaps between segments longer than min_silence_s.

    Phase 1 only looks at gaps BETWEEN transcript segments (i.e. silence
    where nobody is talking at all) -- it does not attempt sub-word
    breath/pause detection, which would need raw audio analysis beyond
    this rule's scope.
    """

    config = config or PlannerConfig()
    ops = []
    segs = transcript.segments
    for prev, nxt in zip(segs, segs[1:]):
        gap = nxt.start - prev.end
        if gap >= config.min_silence_s:
            start = prev.end + config.silence_pad_s
            end = nxt.start - config.silence_pad_s
            if end > start:
                ops.append({
                    "type": "cut",
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "reason": f"silence gap of {gap:.2f}s",
                })
    return ops
