"""Assemble planner rules into a full edit plan operations list."""

from __future__ import annotations

from .models import PlannerConfig
from .rules import (
    generate_broll_suggestions,
    generate_captions,
    generate_emphasis,
    generate_silence_cuts,
    generate_zooms,
)


def generate_operations(transcript, config: PlannerConfig = None):
    """Run all Phase 1 rules and return a single, time-sorted operations list."""

    config = config or PlannerConfig()

    emphasis_ops = generate_emphasis(transcript, config)
    operations = []
    operations += generate_silence_cuts(transcript, config)
    operations += generate_captions(transcript, config)
    operations += emphasis_ops
    operations += generate_zooms(transcript, config, emphasis_ops=emphasis_ops)
    operations += generate_broll_suggestions(transcript, config)

    def sort_key(op):
        return op.get("start", op.get("at", 0.0))

    operations.sort(key=sort_key)
    return operations


def generate_edit_plan(transcript, media_path: str, project: dict, config: PlannerConfig = None) -> dict:
    """Build a full, schema-shaped edit plan dict (not yet validated).

    ``project`` must match the pre-existing $defs/project shape from
    schemas/edit_plan.schema.json, e.g. {"width": 1080, "height": 1920, "fps": 30}.

    The legacy "modules" field is included as an empty list so the plan
    still satisfies the pre-existing (unchanged) required field -- Phase 1
    plans are additive, not a replacement of the module-toggle system.
    """

    config = config or PlannerConfig()

    return {
        "schema_version": "1.1.0-phase1",
        "project": project,
        "modules": [],
        "source": {
            "media": media_path,
            "duration": transcript.duration if transcript.duration is not None else 0.0,
        },
        "segments": [seg.to_dict() for seg in transcript.segments],
        "operations": generate_operations(transcript, config),
        "metadata": {
            "generator": "editiq.planner (Phase 1, rules-based, deterministic)",
            "language": transcript.language,
        },
    }
