"""
Test suite for Word-Level Reference Caption Analysis
(analyzer/word_level_analyzer.py).

Runs as a plain script (same convention as
tests/test_style_profile_engine.py) -- every test_* function is
discovered and run, PASS/FAIL is printed per test, and the process
exits non-zero if anything fails.

These tests use REAL Tesseract OCR against synthetically rendered
caption frames (drawn with OpenCV) -- not mocked OCR output. This is
a genuine, executable end-to-end check of the OCR -> tracking ->
clustering pipeline, just without a real reference video.

Run with:  python3 tests/test_word_level_analyzer.py
"""

import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analyzer.word_level_analyzer import (  # noqa: E402
    analyze_word_styles,
    ocr_words_in_region,
    cluster_word_styles,
)
from schemas.validate import validate_style_profile  # noqa: E402
from analyzer.reference_analyzer import analyze_video  # noqa: E402


FRAME_W, FRAME_H = 1000, 300
CAPTION_REGION = {"x": 0, "y": 80, "width": FRAME_W, "height": 180}


def _blank_frame():
    return np.full((FRAME_H, FRAME_W, 3), 25, dtype=np.uint8)


def _draw_words(frame, words_xy_color_scale):
    """words_xy_color_scale: list of (text, x, y, color_bgr, font_scale, thickness)"""
    for text, x, y, color, font_scale, thickness in words_xy_color_scale:
        cv2.putText(
            frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
            font_scale, color, thickness, cv2.LINE_AA
        )
    return frame


def _samples_from_frames(frames, times=None):
    if times is None:
        times = [round(i * 0.5, 3) for i in range(len(frames))]
    return [
        {"frame_number": i, "time_seconds": times[i], "frame": frames[i]}
        for i in range(len(frames))
    ]


# ---------------------------------------------------------------------
# Test 1: Uniform caption -> no unnecessary word_styles
# ---------------------------------------------------------------------

def test_uniform_caption_produces_no_word_styles():
    frame = _blank_frame()
    _draw_words(frame, [
        ("THIS", 40, 190, (255, 255, 255), 1.8, 3),
        ("IS", 260, 190, (255, 255, 255), 1.8, 3),
        ("UNIFORM", 400, 190, (255, 255, 255), 1.8, 3),
    ])
    samples = _samples_from_frames([frame, frame.copy()])

    result = analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="FAST")

    assert result["word_analysis"]["attempted"] is True
    assert result["word_analysis"]["success"] is True, result["word_analysis"]
    assert len(result["word_detections"]) >= 2, "expected multiple words tracked"
    assert result["word_styles"] == {}, f"uniform caption should yield no word_styles, got {result['word_styles']}"
    for detection in result["word_detections"]:
        assert "style_name" not in detection, detection


# ---------------------------------------------------------------------
# Test 2: One differently colored word -> word-level color detection
# ---------------------------------------------------------------------

def test_color_emphasis_word_detected():
    frame = _blank_frame()
    _draw_words(frame, [
        ("THIS", 40, 190, (255, 255, 255), 1.8, 3),
        ("IS", 260, 190, (255, 255, 255), 1.8, 3),
        ("GREEN", 400, 190, (60, 220, 60), 1.8, 3),   # BGR green, distinct
        ("WORD", 650, 190, (255, 255, 255), 1.8, 3),
    ])
    samples = _samples_from_frames([frame, frame.copy(), frame.copy()])

    result = analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="FAST")

    assert result["word_analysis"]["success"] is True, result["word_analysis"]
    green_detection = next(
        (d for d in result["word_detections"] if d["text"].upper() == "GREEN"), None
    )
    assert green_detection is not None, [d["text"] for d in result["word_detections"]]
    assert "style_name" in green_detection, "GREEN word should have been flagged as emphasized"
    style = result["word_styles"][green_detection["style_name"]]
    assert "fill" in style, f"expected a fill override for the color-emphasized word, got {style}"

    # Non-deviating words must NOT be flagged.
    for d in result["word_detections"]:
        if d["text"].upper() != "GREEN":
            assert "style_name" not in d, f"unexpected emphasis on uniform word: {d}"


# ---------------------------------------------------------------------
# Test 3: One larger word -> scale detection
# ---------------------------------------------------------------------

def test_size_emphasis_word_detected():
    frame = _blank_frame()
    _draw_words(frame, [
        ("SMALL", 40, 190, (255, 255, 255), 1.4, 3),
        ("WORDS", 260, 190, (255, 255, 255), 1.4, 3),
    ])
    # Draw one clearly bigger word further right, same color.
    cv2.putText(frame, "BIG", 480, cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1) if False else None
    cv2.putText(frame, "BIG", (480, 220), cv2.FONT_HERSHEY_SIMPLEX, 2.6, (255, 255, 255), 5, cv2.LINE_AA)

    samples = _samples_from_frames([frame, frame.copy()])
    result = analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="FAST")

    assert result["word_analysis"]["success"] is True, result["word_analysis"]
    big_detection = next((d for d in result["word_detections"] if d["text"].upper() == "BIG"), None)
    assert big_detection is not None, [d["text"] for d in result["word_detections"]]
    assert big_detection["relative_scale"] > 1.15, big_detection
    assert "style_name" in big_detection, "BIG word should have been flagged as emphasized (scale)"
    style = result["word_styles"][big_detection["style_name"]]
    assert "scale" in style, f"expected a scale override, got {style}"


# ---------------------------------------------------------------------
# Test 4: One bold word -> weight estimate where technically detectable
# ---------------------------------------------------------------------

def test_weight_signal_estimated_for_bold_word():
    frame = _blank_frame()
    _draw_words(frame, [
        ("NORMAL", 40, 190, (255, 255, 255), 1.6, 2),
        ("TEXT", 320, 190, (255, 255, 255), 1.6, 2),
    ])
    # Thicker stroke (bold proxy) -- also naturally a bit larger, which is
    # realistic (bold glyphs occupy more area) and lets the weak weight
    # signal be corroborated rather than trusted alone.
    cv2.putText(frame, "BOLD", (520, 195), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (255, 255, 255), 7, cv2.LINE_AA)

    samples = _samples_from_frames([frame, frame.copy()])
    result = analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="FAST")

    assert result["word_analysis"]["success"] is True, result["word_analysis"]
    bold_detection = next((d for d in result["word_detections"] if d["text"].upper() == "BOLD"), None)
    assert bold_detection is not None, [d["text"] for d in result["word_detections"]]
    # The weight/ink-density signal must at minimum be *measured* and
    # reported, even if -- per spec -- a single weak signal alone would
    # not be enough to justify emphasis without corroboration.
    assert "relative_weight" in bold_detection
    assert bold_detection["relative_weight"] > 1.0, (
        "bold glyph should show higher ink-ratio density than normal text: "
        f"{bold_detection}"
    )


# ---------------------------------------------------------------------
# Test 5: Animated word -> animation/emphasis metadata where detectable
# ---------------------------------------------------------------------

def test_animated_word_detected():
    frames = []
    base_x = 300
    for step in range(5):
        frame = _blank_frame()
        _draw_words(frame, [
            ("STATIC", 40, 190, (255, 255, 255), 1.6, 3),
        ])
        # This word visibly moves/grows across frames -- animation evidence.
        moving_x = base_x + step * 30
        scale = 1.4 + step * 0.15
        cv2.putText(
            frame, "POP", (moving_x, 200), cv2.FONT_HERSHEY_SIMPLEX,
            scale, (255, 255, 255), 3, cv2.LINE_AA
        )
        frames.append(frame)

    samples = _samples_from_frames(frames)
    result = analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="QUALITY")

    assert result["word_analysis"]["success"] is True, result["word_analysis"]
    pop_detection = next((d for d in result["word_detections"] if d["text"].upper() == "POP"), None)
    assert pop_detection is not None, [d["text"] for d in result["word_detections"]]
    assert pop_detection.get("animation_hint") == "position_or_scale_change", pop_detection


# ---------------------------------------------------------------------
# Test 6: Legacy / fallback -- OCR failure must not break the profile
# ---------------------------------------------------------------------

def test_ocr_failure_falls_back_to_valid_global_profile(monkeypatch=None):
    import analyzer.word_level_analyzer as wla

    original_flag = wla._PYTESSERACT_AVAILABLE
    original_pytesseract = wla.pytesseract
    try:
        # Simulate Tesseract/pytesseract being entirely unavailable.
        wla._PYTESSERACT_AVAILABLE = False
        wla.pytesseract = None

        frame = _blank_frame()
        _draw_words(frame, [("HELLO", 40, 190, (255, 255, 255), 1.6, 3)])
        samples = _samples_from_frames([frame])

        result = wla.analyze_word_styles(samples, CAPTION_REGION, fps=24, mode="FAST")

        assert result["word_analysis"]["attempted"] is True
        assert result["word_analysis"]["success"] is False
        assert result["word_detections"] == []
        assert result["word_styles"] == {}
    finally:
        wla._PYTESSERACT_AVAILABLE = original_flag
        wla.pytesseract = original_pytesseract


def test_analyze_video_still_returns_valid_profile_when_ocr_unavailable():
    """
    End-to-end: build a tiny real video with ffmpeg from a single drawn
    frame, then run the *actual* analyze_video() entry point with OCR
    forced unavailable, and confirm the resulting profile still
    validates against the schema (the mandatory fallback contract).
    """
    import tempfile
    import subprocess
    import analyzer.word_level_analyzer as wla

    frame = _blank_frame()
    _draw_words(frame, [("HELLO", 40, 190, (255, 255, 255), 1.6, 3)])

    with tempfile.TemporaryDirectory() as tmp:
        frame_path = str(Path(tmp) / "frame.png")
        video_path = str(Path(tmp) / "clip.mp4")
        cv2.imwrite(frame_path, frame)

        subprocess.run(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", frame_path,
                "-t", "1", "-r", "6", "-pix_fmt", "yuv420p", video_path,
            ],
            check=True, capture_output=True,
        )

        original_flag = wla._PYTESSERACT_AVAILABLE
        try:
            wla._PYTESSERACT_AVAILABLE = False
            profile = analyze_video(video_path, mode="FAST")
        finally:
            wla._PYTESSERACT_AVAILABLE = original_flag

        validate_style_profile(profile)  # must not raise
        assert profile["word_analysis"]["attempted"] is True
        assert profile["word_analysis"]["success"] is False
        assert "word_detections" not in profile


def _run_all_tests():
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]

    passed = 0
    failed = []

    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
            passed += 1
        except AssertionError as error:
            print(f"FAIL  {test.__name__}: {error}")
            failed.append(test.__name__)
        except Exception as error:  # noqa: BLE001
            print(f"ERROR {test.__name__}: {type(error).__name__}: {error}")
            failed.append(test.__name__)

    print(f"\n{passed}/{len(tests)} passed")

    if failed:
        print("Failed:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    _run_all_tests()
