import json
import subprocess
import sys


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "editiq", *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )

import os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_plan_with_mock_backend(tmp_path):
    out = tmp_path / "plan.json"
    result = _run_cli("plan", "nonexistent.mp4", "--backend", "mock", "--output", str(out))
    assert result.returncode == 0, result.stderr
    plan = json.loads(out.read_text())
    assert "operations" in plan
    assert plan["modules"] == []


def test_cli_transcribe_with_mock_backend():
    result = _run_cli("transcribe", "nonexistent.mp4", "--backend", "mock")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "segments" in data
    assert data["language"] == "en"


def test_cli_analyze_missing_file_does_not_crash():
    result = _run_cli("analyze", "definitely_missing_file.mp4")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["media"] == "definitely_missing_file.mp4"
    # ffprobe will fail on a nonexistent file -> duration is None, not a crash
    assert data["duration"] is None
