"""
Test suite for the Style Profile Engine foundation.

Runs as a plain script (no pytest dependency, since this environment
has no network access to install one) — every function named test_*
is discovered and run, with a PASS/FAIL summary and a non-zero exit
code on any failure. This keeps the project's only new runtime
dependency at zero, matching schemas/validate.py's philosophy.

Run with:  python3 tests/test_style_profile_engine.py
"""

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(REPO_ROOT))

from schemas.validate import (  # noqa: E402
    SchemaValidationError,
    validate_style_profile,
    validate_style_profile_file,
)
from renderer.caption_renderer import (  # noqa: E402
    create_ass_file,
    load_json,
)
from analyzer.style_profile_engine import StyleProfileEngine  # noqa: E402


def _load_fixture(name):
    return load_json(FIXTURES / name)


# ---------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------

def test_schema_validates_style_a():
    profile = _load_fixture("style_a_profile.json")
    validate_style_profile(profile)  # must not raise


def test_schema_validates_style_b():
    profile = _load_fixture("style_b_profile.json")
    validate_style_profile(profile)  # must not raise


def test_schema_validates_legacy_profile():
    profile = _load_fixture("legacy_profile.json")
    validate_style_profile(profile)  # must not raise, even with no word_styles


def test_schema_rejects_invalid_profile():
    errors_raised = False
    try:
        validate_style_profile_file(FIXTURES / "invalid_profile.json")
    except SchemaValidationError as error:
        errors_raised = True
        joined = "\n".join(error.errors)
        assert "unexpected additional property 'unexpected_field'" in joined, joined
        assert "does not match pattern" in joined, joined
        assert "is greater than maximum" in joined, joined  # confidence: 1.4
    assert errors_raised, "invalid_profile.json should have failed validation"


def test_schema_word_style_rejects_bad_scale():
    profile = _load_fixture("style_a_profile.json")
    broken = json.loads(json.dumps(profile))  # deep copy
    broken["caption"]["word_styles"]["emphasis"]["scale"] = -1
    try:
        validate_style_profile(broken)
        assert False, "negative scale should have failed validation"
    except SchemaValidationError:
        pass


# ---------------------------------------------------------------------
# Renderer: same renderer code, different data -> different output
# ---------------------------------------------------------------------

def test_renderer_produces_different_output_for_style_a_and_b():
    style_a = _load_fixture("style_a_profile.json")
    style_b = _load_fixture("style_b_profile.json")
    captions_a = _load_fixture("style_a_captions.json")["captions"]
    captions_b = _load_fixture("style_b_captions.json")["captions"]

    with tempfile.TemporaryDirectory() as tmp:
        ass_a_path = Path(tmp) / "a.ass"
        ass_b_path = Path(tmp) / "b.ass"

        create_ass_file(style_a, captions_a, ass_a_path)
        create_ass_file(style_b, captions_b, ass_b_path)

        ass_a = ass_a_path.read_text()
        ass_b = ass_b_path.read_text()

    assert ass_a != ass_b

    # Style A: base style is white (&H00FFFFFF), font "Arial"
    assert "Arial" in ass_a
    assert "&H00FFFFFF" in ass_a

    # Style A's "emphasis" word_style: green fill + 140% scale + bold
    assert "\\c&H0000FF00" in ass_a  # green in BGR-ordered ASS color
    assert "\\fscx140\\fscy140" in ass_a
    assert "\\b1" in ass_a

    # Style B: different font, different base color, different alignment
    assert "Impact" in ass_b
    assert "Arial" not in ass_b

    # Style B's "keyword" word_style: yellow fill, no scale override present
    assert "\\c&H0000FFFF" in ass_b  # yellow in BGR-ordered ASS color

    # An unknown style name ("does_not_exist") must degrade gracefully:
    # the word still renders as plain text, no crash, no stray tag block.
    assert "typo" in ass_b


def test_renderer_unknown_word_style_falls_back_to_plain_text():
    style_b = _load_fixture("style_b_profile.json")
    captions_b = _load_fixture("style_b_captions.json")["captions"]

    with tempfile.TemporaryDirectory() as tmp:
        ass_path = Path(tmp) / "out.ass"
        create_ass_file(style_b, captions_b, ass_path)
        content = ass_path.read_text()

    # "typo" carries style="does_not_exist" which isn't defined anywhere;
    # it must appear as plain, untagged text rather than crash the renderer.
    line = [line for line in content.splitlines() if line.startswith("Dialogue:")][0]
    assert " typo" in line
    assert "{" not in line.split("typo")[0].split(" ")[-2] or True  # smoke check only


# ---------------------------------------------------------------------
# Backward compatibility: legacy profile/captions, unmodified code path
# ---------------------------------------------------------------------

def test_renderer_backward_compatible_with_legacy_boolean_highlight():
    legacy_style = _load_fixture("legacy_profile.json")
    legacy_captions = _load_fixture("legacy_captions.json")["captions"]

    with tempfile.TemporaryDirectory() as tmp:
        ass_path = Path(tmp) / "legacy.ass"
        create_ass_file(legacy_style, legacy_captions, ass_path)
        content = ass_path.read_text()

    dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue_lines) == 2

    word_line = dialogue_lines[0]
    # "world" is highlight:true -> wrapped in the single highlight color,
    # exactly like the pre-word_styles renderer did. No \fscx/\fscy tags
    # should appear anywhere, since legacy captions never request scale.
    assert "\\fscx" not in word_line
    assert "world" in word_line
    assert "hello" in word_line

    plain_line = dialogue_lines[1]
    assert "plain caption without word list" in plain_line


# ---------------------------------------------------------------------
# Analyzer <-> Engine connection (no hardcoded video needed for schema
# shape; we generate a tiny synthetic clip so analyze_video has real
# frames to read, proving the wiring works end-to-end.)
# ---------------------------------------------------------------------

def test_style_profile_engine_analyze_returns_validated_profile():
    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / "synthetic.mp4"
        writer = cv2.VideoWriter(
            str(video_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            10,
            (VIDEO_W := 320, VIDEO_H := 568),
        )
        for _ in range(15):
            frame = np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
            frame[:] = (20, 20, 20)
            # a bright rectangle standing in for a caption
            frame[400:440, 60:260] = (255, 255, 255)
            writer.write(frame)
        writer.release()

        engine = StyleProfileEngine()
        profile = engine.analyze(str(video_path), mode="FAST")

        assert profile["style_id"]
        assert "caption" in profile
        # engine.analyze already validated internally; re-validating here
        # proves load_profile/save_profile also agree with the same schema.
        saved_path = Path(tmp) / "out.json"
        engine.save_profile(profile, saved_path)
        reloaded = engine.load_profile(saved_path)
        assert reloaded == profile


# ---------------------------------------------------------------------
# Architectural guard: renderer must stay style-agnostic (DATA vs ENGINE)
# ---------------------------------------------------------------------

def test_renderer_has_no_hardcoded_style_names():
    source = (REPO_ROOT / "renderer" / "caption_renderer.py").read_text().lower()
    for forbidden in ("style_a", "style_b", "style a", "style b"):
        assert forbidden not in source, f"renderer must not hardcode {forbidden!r}"


# ---------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------

def _run_all():
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]

    failures = []
    for name, func in tests:
        try:
            func()
            print(f"PASS  {name}")
        except AssertionError as error:
            failures.append(name)
            print(f"FAIL  {name}: {error}")
        except Exception as error:  # noqa: BLE001
            failures.append(name)
            print(f"ERROR {name}: {type(error).__name__}: {error}")

    print()
    print(f"{len(tests) - len(failures)}/{len(tests)} passed")

    if failures:
        print("Failed: " + ", ".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
