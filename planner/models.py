"""Planner configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlannerConfig:
    # Silence cuts
    min_silence_s: float = 0.8
    silence_pad_s: float = 0.1

    # Emphasis: words at/above this length (chars) or matching keywords
    # below are candidates for emphasis + a restrained zoom.
    emphasis_min_word_len: int = 7
    emphasis_keywords: tuple = ("never", "always", "free", "today", "now", "guarantee")
    max_emphasis_per_segment: int = 1

    # Zoom
    zoom_scale: float = 1.12
    zoom_pad_s: float = 0.15

    # B-roll: naive keyword-triggered concept suggestions. This is NOT an
    # asset downloader -- it only proposes a search query per hit.
    broll_keywords: dict = field(default_factory=lambda: {
        "money": "close-up of cash and coins",
        "bank": "person checking bank account on phone",
        "invest": "stock market chart animation",
        "save": "piggy bank with coins",
        "work": "person working at a desk",
        "idle": "clock ticking, wasted time",
    })
