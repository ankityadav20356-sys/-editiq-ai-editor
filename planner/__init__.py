"""Rules-based Phase 1 edit planner.

Deterministic: given the same transcript and config, always produces the
same operations in the same order. No LLM calls, no randomness.
"""

from .generator import generate_edit_plan
from .rules import (
    generate_broll_suggestions,
    generate_captions,
    generate_emphasis,
    generate_silence_cuts,
    generate_zooms,
)

__all__ = [
    "generate_edit_plan",
    "generate_captions",
    "generate_emphasis",
    "generate_zooms",
    "generate_broll_suggestions",
    "generate_silence_cuts",
]
