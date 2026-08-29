"""Pipeline orchestration: media -> analysis -> transcription -> normalize
-> segment -> plan -> validate -> edit_plan.json.

Usable both programmatically (``run_pipeline(...)``) and via the CLI
(editiq/cli.py).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

from planner.generator import generate_edit_plan
from planner.models import PlannerConfig
from schemas.edit_plan_validate import validate_edit_plan
from transcription.backend import TranscriptionBackend
from transcription.mock_backend import MockTranscriptionBackend
from transcription.normalize import normalize_transcript
from transcription.segment import SegmentationConfig, segment_transcript


def probe_media_duration(media_path: str) -> Optional[float]:
    """Best-effort media duration via ffprobe. Returns None if unavailable.

    This is intentionally best-effort and non-fatal: if ffprobe isn't
    installed or the file can't be probed, the pipeline falls back to the
    transcript's own reported duration rather than failing outright.
    """

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", media_path,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def analyze_media(media_path: str) -> dict:
    """Phase 1 media analysis: currently just duration probing via ffprobe.

    This is deliberately minimal -- it does not do scene detection, visual
    analysis, or anything the analyzer/ package already handles for
    style-profile matching. Phase 1's "analyze" step exists so the CLI and
    pipeline have a stable place to plug in richer analysis later without
    changing the public pipeline signature.
    """

    duration = probe_media_duration(media_path)
    return {"media": media_path, "duration": duration}


def run_pipeline(
    media_path: str,
    project: dict,
    backend: Optional[TranscriptionBackend] = None,
    segmentation_config: Optional[SegmentationConfig] = None,
    planner_config: Optional[PlannerConfig] = None,
    validate: bool = True,
) -> dict:
    """Run the full Phase 1 pipeline and return a validated edit plan dict.

    ``backend`` defaults to MockTranscriptionBackend so the pipeline is
    runnable without a real ML model; pass a
    transcription.faster_whisper_backend.FasterWhisperBackend for real
    transcription.
    """

    backend = backend or MockTranscriptionBackend()

    analysis = analyze_media(media_path)

    transcript = backend.transcribe(media_path)
    transcript = normalize_transcript(transcript)
    transcript = segment_transcript(transcript, segmentation_config)

    plan = generate_edit_plan(transcript, media_path, project, planner_config)

    # Prefer a real ffprobe-measured duration over the ASR backend's own
    # (sometimes approximate) duration estimate, when available.
    media_duration = analysis.get("duration")
    if media_duration is not None:
        plan["source"]["duration"] = media_duration
    else:
        media_duration = plan["source"]["duration"]

    if validate:
        validate_edit_plan(plan, media_duration=media_duration)

    return plan


def run_pipeline_to_file(media_path: str, project: dict, output_path: str, **kwargs) -> dict:
    plan = run_pipeline(media_path, project, **kwargs)
    Path(output_path).write_text(json.dumps(plan, indent=2))
    return plan
