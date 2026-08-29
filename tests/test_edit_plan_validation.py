import pytest

from schemas.edit_plan_validate import validate_edit_plan, SchemaValidationError
from planner.generator import generate_edit_plan
from transcription.mock_backend import MockTranscriptionBackend
from transcription.normalize import normalize_transcript
from transcription.segment import segment_transcript


def _valid_plan():
    backend = MockTranscriptionBackend(script="Your money should never sit idle. Put it to work today.")
    t = segment_transcript(normalize_transcript(backend.transcribe("x.mp4")))
    project = {"width": 1080, "height": 1920, "fps": 30}
    return generate_edit_plan(t, "video.mp4", project), t.duration


def test_valid_plan_passes():
    plan, duration = _valid_plan()
    validate_edit_plan(plan, media_duration=duration)  # should not raise


def test_missing_required_top_level_field_fails():
    plan, duration = _valid_plan()
    del plan["schema_version"]
    with pytest.raises(SchemaValidationError):
        validate_edit_plan(plan, media_duration=duration)


def test_caption_missing_text_fails_semantics():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "caption", "start": 0.0, "end": 1.0})
    with pytest.raises(SchemaValidationError) as exc:
        validate_edit_plan(plan, media_duration=duration)
    assert any("text" in e for e in exc.value.errors)


def test_start_after_end_fails():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "cut", "start": 5.0, "end": 2.0})
    with pytest.raises(SchemaValidationError) as exc:
        validate_edit_plan(plan, media_duration=duration)
    assert any("end" in e and "start" in e for e in exc.value.errors)


def test_negative_start_fails():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "cut", "start": -1.0, "end": 2.0})
    with pytest.raises(SchemaValidationError) as exc:
        validate_edit_plan(plan, media_duration=duration)
    assert any("negative" in e for e in exc.value.errors)


def test_timestamp_beyond_media_duration_fails():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "cut", "start": 0.0, "end": duration + 100})
    with pytest.raises(SchemaValidationError) as exc:
        validate_edit_plan(plan, media_duration=duration)
    assert any("exceeds media duration" in e for e in exc.value.errors)


def test_overlapping_captions_fail():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "caption", "start": 0.0, "end": 1.0, "text": "a"})
    plan["operations"].append({"type": "caption", "start": 0.5, "end": 1.5, "text": "b"})
    with pytest.raises(SchemaValidationError) as exc:
        validate_edit_plan(plan, media_duration=duration)
    assert any("overlapping" in e for e in exc.value.errors)


def test_overlapping_broll_is_allowed():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "broll", "start": 0.0, "end": 2.0, "query": "a"})
    plan["operations"].append({"type": "broll", "start": 1.0, "end": 3.0, "query": "b"})
    validate_edit_plan(plan, media_duration=max(duration, 3.0))  # should not raise


def test_transition_uses_at_not_start_end():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "transition", "at": 1.0, "style": "cut"})
    validate_edit_plan(plan, media_duration=duration)  # should not raise


def test_unknown_operation_type_fails():
    plan, duration = _valid_plan()
    plan["operations"].append({"type": "not_a_real_type", "start": 0.0, "end": 1.0})
    with pytest.raises(SchemaValidationError):
        validate_edit_plan(plan, media_duration=duration)
