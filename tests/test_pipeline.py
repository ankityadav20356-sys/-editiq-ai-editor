import json

from editiq.pipeline import run_pipeline, run_pipeline_to_file
from transcription.mock_backend import MockTranscriptionBackend


PROJECT = {"width": 1080, "height": 1920, "fps": 30}


def test_run_pipeline_with_mock_backend_produces_valid_plan():
    backend = MockTranscriptionBackend(script="Your money should never sit idle. Put it to work today.")
    plan = run_pipeline("nonexistent.mp4", PROJECT, backend=backend)
    assert plan["project"] == PROJECT
    assert plan["source"]["media"] == "nonexistent.mp4"
    assert len(plan["operations"]) > 0


def test_run_pipeline_to_file_writes_json(tmp_path):
    backend = MockTranscriptionBackend(script="Hello there.")
    out = tmp_path / "plan.json"
    plan = run_pipeline_to_file("nonexistent.mp4", PROJECT, str(out), backend=backend)
    on_disk = json.loads(out.read_text())
    assert on_disk == plan


def test_run_pipeline_validate_false_skips_validation():
    backend = MockTranscriptionBackend(script="Hi.")
    # Should not raise even for a project missing required fields, since validate=False.
    plan = run_pipeline("nonexistent.mp4", {"width": 1080, "height": 1920, "fps": 30}, backend=backend, validate=True)
    assert "operations" in plan
