"""
Word-Level Reference Caption Analysis.

    REFERENCE VIDEO (frames already sampled by reference_analyzer)
        -> caption region (from reference_analyzer.detect_caption_region)
        -> Tesseract OCR                        (ocr_words_in_region)
        -> word bounding boxes
        -> temporal word tracking                (track_words_across_frames)
        -> visual signal extraction per word      (extract_word_signal)
        -> word_detections                        (raw evidence)
        -> word style clustering                  (cluster_word_styles)
        -> word_styles                            (renderer-facing, named)
        -> merged into the validated STYLE PROFILE by reference_analyzer.analyze_video

This module intentionally does NOT reimplement caption-region detection,
color estimation, or global style logic — all of that stays in
reference_analyzer.py untouched. This module only adds word-level detail
on top of it.

HARD REQUIREMENT: nothing in this module may raise out to the caller in
a way that breaks the overall analysis. Every public entry point catches
its own failures and degrades to an empty/low-confidence result instead.
When that happens, reference_analyzer.py keeps using its existing global
caption profile — this module only ever *adds* detail, never removes or
blocks it.
"""

from collections import Counter, defaultdict

import numpy as np
import cv2

try:
    import pytesseract
    _PYTESSERACT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via fallback tests
    pytesseract = None
    _PYTESSERACT_AVAILABLE = False


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


# ---------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------

def ocr_words_in_region(frame, region, min_confidence=40):
    """
    Run Tesseract OCR (image_to_data) over the caption region of a single
    frame and return detected words with absolute-frame pixel bounding
    boxes and normalized (0-1) OCR confidence.

    Returns [] — never None, never raises — on any failure: Tesseract not
    installed, pytesseract not importable, empty/invalid crop, or an
    OCR engine error. Callers must treat "OCR unavailable" and "OCR ran
    but found nothing" identically: both are an empty word list.
    """
    if not _PYTESSERACT_AVAILABLE or frame is None:
        return []

    try:
        height, width = frame.shape[:2]
    except Exception:
        return []

    if region:
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("width", 0))
        h = int(region.get("height", 0))
        pad = max(4, int(min(max(w, 1), max(h, 1)) * 0.15))
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(width, x + w + pad), min(height, y + h + pad)
    else:
        # No detected region: fall back to the lower portion of the
        # frame, where captions conventionally sit.
        x1, y1, x2, y2 = 0, int(height * 0.55), width, height

    if x2 <= x1 or y2 <= y1:
        return []

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return []

    data = None

    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        data = pytesseract.image_to_data(
            thresh, config="--psm 11", output_type=pytesseract.Output.DICT
        )
    except Exception:
        data = None

    if data is None:
        try:
            data = pytesseract.image_to_data(
                crop, config="--psm 11", output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []

    words = []
    count = len(data.get("text", []) or [])

    for index in range(count):
        text = (data["text"][index] or "").strip()

        if not text:
            continue

        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError, KeyError):
            confidence = -1.0

        if confidence < min_confidence:
            continue

        try:
            word_x = int(data["left"][index]) + x1
            word_y = int(data["top"][index]) + y1
            word_w = int(data["width"][index])
            word_h = int(data["height"][index])
        except (ValueError, TypeError, KeyError):
            continue

        if word_w <= 0 or word_h <= 0:
            continue

        words.append({
            "text": text,
            "bbox": (word_x, word_y, word_w, word_h),
            "confidence": round(_clamp(confidence / 100.0, 0.0, 1.0), 3),
        })

    return words


# ---------------------------------------------------------------------
# Temporal tracking
# ---------------------------------------------------------------------

def _iou(box_a, box_b):
    ax1, ay1 = box_a[0], box_a[1]
    ax2, ay2 = box_a[0] + box_a[2], box_a[1] + box_a[3]
    bx1, by1 = box_b[0], box_b[1]
    bx2, by2 = box_b[0] + box_b[2], box_b[1] + box_b[3]

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)

    inter_w, inter_h = max(0, ix2 - ix1), max(0, iy2 - iy1)
    intersection = inter_w * inter_h

    area_a = max(box_a[2], 0) * max(box_a[3], 0)
    area_b = max(box_b[2], 0) * max(box_b[3], 0)
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def track_words_across_frames(frame_word_lists, frame_times, iou_threshold=0.25):
    """
    Link OCR detections of the same word across consecutive sampled
    frames using text equality plus bounding-box IoU/proximity.

    `frame_word_lists[i]` are the words returned by ocr_words_in_region
    for sampled frame i; `frame_times[i]` is that frame's timestamp.

    Returns a list of tracks:
        {
            "text": str,
            "boxes": [bbox, ...],          # one per frame it appeared in
            "confidences": [float, ...],
            "first_time": float,
            "last_time": float,
            "frame_indices": [int, ...],
        }

    This is a best-effort tracker (text similarity + IoU), not a
    guaranteed-correct one — animation, occlusion, or OCR misreads can
    still fragment a track. Fragmentation degrades detail, not
    correctness: each fragment still becomes a valid (lower-confidence)
    track rather than corrupting another word's data.
    """
    tracks = []
    open_tracks = []  # tracks still eligible to extend on this frame

    for frame_index, words in enumerate(frame_word_lists):
        time_seconds = frame_times[frame_index] if frame_index < len(frame_times) else 0.0
        matched_this_frame = set()

        for track in open_tracks:
            last_box = track["boxes"][-1]
            best_match = None
            best_score = 0.0

            for word_index, word in enumerate(words):
                if word_index in matched_this_frame:
                    continue
                if word["text"].lower() != track["text"].lower():
                    continue

                score = _iou(last_box, word["bbox"])

                if score > best_score:
                    best_score = score
                    best_match = word_index

            if best_match is not None and best_score >= iou_threshold:
                word = words[best_match]
                track["boxes"].append(word["bbox"])
                track["confidences"].append(word["confidence"])
                track["last_time"] = time_seconds
                track["frame_indices"].append(frame_index)
                matched_this_frame.add(best_match)
                track["_active"] = True
            else:
                track["_active"] = False

        for word_index, word in enumerate(words):
            if word_index in matched_this_frame:
                continue

            new_track = {
                "text": word["text"],
                "boxes": [word["bbox"]],
                "confidences": [word["confidence"]],
                "first_time": time_seconds,
                "last_time": time_seconds,
                "frame_indices": [frame_index],
                "_active": True,
            }
            open_tracks.append(new_track)

        # Tracks that failed to extend this frame are closed out (kept
        # in the final result either way — "_active" only controls
        # whether they can still be extended going forward).
        still_open = [track for track in open_tracks if track["_active"]]
        newly_closed = [track for track in open_tracks if not track["_active"]]

        for track in newly_closed:
            del track["_active"]
            tracks.append(track)

        open_tracks = still_open

    for track in open_tracks:
        del track["_active"]
        tracks.append(track)

    return tracks


# ---------------------------------------------------------------------
# Visual signal extraction
# ---------------------------------------------------------------------

def extract_word_signal(frame, bbox):
    """
    Sample a single word's bounding box in a single frame and estimate:
      - fill: dominant text color (#RRGGBB)
      - ink_ratio: fraction of the bbox that is "ink" (foreground glyph
        pixels vs background) — a rough, deliberately-approximate proxy
        for stroke/font weight, since real font-weight identification
        is out of scope for this milestone.

    Returns None if the crop is empty or degenerate.
    """
    x, y, w, h = bbox

    if w <= 0 or h <= 0:
        return None

    height, width = frame.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + w), min(height, y + h)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Otsu splits the crop into "ink" (text) vs "background". Which side
    # is the ink depends on whether the text is lighter or darker than
    # its background, so pick the minority class as ink when it's a
    # plausible glyph coverage ratio (roughly 5%-70% of the box).
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Pick whichever of the two Otsu clusters is actually brighter as
    # "ink" -- caption text in this pipeline is consistently the bright
    # element against a darker background (matching the same assumption
    # reference_analyzer.detect_caption_region/estimate_caption_color
    # already make). This is more robust than assuming ink is always the
    # minority-area cluster: a heavy/bold glyph can easily cover more
    # than half of its own tight OCR bounding box.
    bright_cluster_mean = float(np.mean(gray[thresh > 0])) if np.count_nonzero(thresh) else -1.0
    dark_cluster_mean = float(np.mean(gray[thresh == 0])) if np.count_nonzero(thresh == 0) else -1.0
    ink_mask = thresh if bright_cluster_mean >= dark_cluster_mean else cv2.bitwise_not(thresh)
    ink_ratio = float(np.count_nonzero(ink_mask)) / float(ink_mask.size)

    ink_pixels = crop[ink_mask > 0]

    if len(ink_pixels) < 4:
        # Not enough foreground pixels sampled — fall back to the
        # brightest pixels in the crop as a best-effort estimate.
        gray_flat = gray.flatten()
        if gray_flat.size == 0:
            return None
        bright_threshold = np.percentile(gray_flat, 85)
        mask = gray >= bright_threshold
        ink_pixels = crop[mask]
        if len(ink_pixels) < 1:
            return None

    mean_bgr = np.mean(ink_pixels, axis=0)
    b, g, r = [int(_clamp(round(value), 0, 255)) for value in mean_bgr]
    fill = "#{:02X}{:02X}{:02X}".format(r, g, b)

    return {
        "fill": fill,
        "ink_ratio": round(_clamp(ink_ratio, 0.0, 1.0), 4),
        "height_px": h,
    }


# ---------------------------------------------------------------------
# Style clustering
# ---------------------------------------------------------------------

def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _color_distance(hex_a, hex_b):
    ar, ag, ab = _hex_to_rgb(hex_a)
    br, bg, bb = _hex_to_rgb(hex_b)
    return float(np.sqrt((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2))


def cluster_word_styles(word_records):
    """
    Compare each detected word against the modal ("normal") style of the
    caption and flag emphasis candidates.

    `word_records` is a list of dicts, one per tracked word, each with:
        text, start, end, confidence, fill, height_px, ink_ratio,
        moved (bool, animation evidence)

    Returns (word_detections, word_styles):
      - word_detections: word_records enriched with relative_scale,
        relative_weight, emphasis_score, and (if emphasized) style_name.
      - word_styles: dict of named, deduplicated renderer-facing style
        overrides (fill / scale / font_weight only — matching what
        renderer/caption_renderer.py currently applies per word).

    Design intent: a single weak signal should not be enough to flag a
    word as emphasized. Color is treated as a strong signal on its own
    (it's sampled directly from pixels, not inferred). Scale is treated
    as a moderately strong signal on its own (also a direct geometric
    measurement). Weight (ink-ratio density) is noisy in isolation and
    is only trusted when corroborated by scale, color, or motion.
    A uniform caption (no word deviates) must produce zero word_styles.
    """
    if not word_records:
        return [], {}

    heights = [record["height_px"] for record in word_records if record.get("height_px")]
    median_height = float(np.median(heights)) if heights else 1.0

    ink_ratios = [record["ink_ratio"] for record in word_records if record.get("ink_ratio") is not None]
    median_ink = float(np.median(ink_ratios)) if ink_ratios else 0.0

    colors = [record["fill"] for record in word_records if record.get("fill")]
    if colors:
        rgb_values = [_hex_to_rgb(c) for c in colors]
        modal_fill = "#{:02X}{:02X}{:02X}".format(
            int(round(float(np.median([v[0] for v in rgb_values])))),
            int(round(float(np.median([v[1] for v in rgb_values])))),
            int(round(float(np.median([v[2] for v in rgb_values])))),
        )
    else:
        modal_fill = "#FFFFFF"
    # A color-distance threshold, not exact/bucket equality: real
    # per-word sampling always has some anti-aliasing noise even on
    # genuinely uniform captions, so exact/bucketed matching produced
    # false positives on uniform text. 45 is a deliberately generous
    # tolerance -- a genuinely distinct color (e.g. green emphasis on
    # white text) is nowhere near this close.
    COLOR_DEVIATION_THRESHOLD = 45.0

    enriched = []
    style_signatures = {}
    word_styles = {}
    next_style_index = 1

    for record in word_records:
        height_px = record.get("height_px") or median_height
        relative_scale = round(height_px / median_height, 3) if median_height > 0 else 1.0

        ink_ratio = record.get("ink_ratio")
        relative_weight = (
            round(ink_ratio / median_ink, 3)
            if ink_ratio is not None and median_ink > 0
            else 1.0
        )

        fill = record.get("fill", modal_fill)
        color_deviates = (
            bool(colors)
            and _color_distance(fill, modal_fill) > COLOR_DEVIATION_THRESHOLD
        )
        scale_deviates = relative_scale >= 1.15 or relative_scale <= 0.85
        weight_deviates_strong = relative_weight >= 1.4
        weight_deviates_weak = relative_weight >= 1.2
        motion_evidence = bool(record.get("moved"))

        signals_hit = sum([
            color_deviates,
            scale_deviates,
            weight_deviates_strong,
            motion_evidence,
        ])

        emphasized = (
            color_deviates
            or scale_deviates
            or weight_deviates_strong
            or (weight_deviates_weak and (scale_deviates or motion_evidence))
        )

        emphasis_score = round(_clamp(
            0.4 * color_deviates
            + 0.3 * scale_deviates
            + 0.2 * weight_deviates_strong
            + 0.1 * motion_evidence,
            0.0,
            1.0,
        ), 3)

        detection = dict(record)
        detection["relative_scale"] = relative_scale
        detection["relative_weight"] = relative_weight
        detection["emphasis_score"] = emphasis_score
        detection.pop("moved", None)
        if motion_evidence:
            detection["animation_hint"] = "position_or_scale_change"

        if emphasized:
            override = {}

            if color_deviates:
                override["fill"] = fill
            if scale_deviates:
                override["scale"] = round(_clamp(relative_scale, 0.5, 3.0), 2)
            if weight_deviates_strong or (weight_deviates_weak and signals_hit >= 2):
                override["font_weight"] = 800

            signature = tuple(sorted(override.items()))

            if signature not in style_signatures:
                style_name = f"emphasis_{next_style_index}"
                next_style_index += 1
                style_signatures[signature] = style_name
                word_styles[style_name] = override

            detection["style_name"] = style_signatures[signature]

        enriched.append(detection)

    return enriched, word_styles


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

def analyze_word_styles(samples, region, fps, mode="FAST"):
    """
    Run the full word-level pipeline over already-sampled frames from
    reference_analyzer.analyze_video.

    `samples` is the same list of {"frame_number", "time_seconds", "frame"}
    dicts reference_analyzer already produced via sample_frames — this
    module does no frame extraction of its own.

    Returns a dict:
        {
          "word_detections": [...],
          "word_styles": {...},
          "word_analysis": {
              "attempted": bool,
              "success": bool,
              "confidence": float,
              "word_count": int,
              "message": str,
          },
        }

    Never raises. On any failure (OCR unavailable, no words found, an
    internal error), returns attempted/success flags reflecting exactly
    what happened, with empty word_detections/word_styles so the caller
    can safely fall back to the existing global-only profile.
    """
    empty_analysis = {
        "word_detections": [],
        "word_styles": {},
        "word_analysis": {
            "attempted": False,
            "success": False,
            "confidence": 0.0,
            "word_count": 0,
            "message": "word-level analysis not attempted",
        },
    }

    if not _PYTESSERACT_AVAILABLE:
        empty_analysis["word_analysis"]["attempted"] = True
        empty_analysis["word_analysis"]["message"] = (
            "pytesseract not installed; falling back to global caption analysis"
        )
        return empty_analysis

    if not samples:
        empty_analysis["word_analysis"]["attempted"] = True
        empty_analysis["word_analysis"]["message"] = "no sampled frames available"
        return empty_analysis

    try:
        frame_word_lists = []
        frame_times = []

        for sample in samples:
            frame = sample.get("frame")
            words = ocr_words_in_region(frame, region)
            frame_word_lists.append(words)
            frame_times.append(sample.get("time_seconds", 0.0))

        total_words_seen = sum(len(words) for words in frame_word_lists)

        if total_words_seen == 0:
            empty_analysis["word_analysis"]["attempted"] = True
            empty_analysis["word_analysis"]["message"] = (
                "OCR ran but detected no words above the confidence "
                "threshold; falling back to global caption analysis"
            )
            return empty_analysis

        tracks = track_words_across_frames(frame_word_lists, frame_times)

        word_records = []

        for track in tracks:
            # Use the frame with the highest OCR confidence for this
            # track's visual-signal sample (most reliable crop).
            best_index = int(np.argmax(track["confidences"]))
            best_frame_index = track["frame_indices"][best_index]
            best_bbox = track["boxes"][best_index]
            best_frame = samples[best_frame_index]["frame"]

            signal = extract_word_signal(best_frame, best_bbox)

            if signal is None:
                continue

            first_box = track["boxes"][0]
            last_box = track["boxes"][-1]
            moved = False

            if len(track["boxes"]) > 1:
                dx = abs(last_box[0] - first_box[0])
                dy = abs(last_box[1] - first_box[1])
                d_height = abs(last_box[3] - first_box[3])
                moved = (
                    dx > 0.03 * max(first_box[2], 1)
                    or dy > 0.03 * max(first_box[3], 1)
                    or d_height > 0.15 * max(first_box[3], 1)
                )

            word_records.append({
                "text": track["text"],
                "start": round(float(track["first_time"]), 3),
                "end": round(float(track["last_time"]), 3),
                "confidence": round(float(np.mean(track["confidences"])), 3),
                "fill": signal["fill"],
                "height_px": signal["height_px"],
                "ink_ratio": signal["ink_ratio"],
                "moved": moved,
            })

        if not word_records:
            empty_analysis["word_analysis"]["attempted"] = True
            empty_analysis["word_analysis"]["message"] = (
                "words were detected but none produced a usable visual "
                "signal; falling back to global caption analysis"
            )
            return empty_analysis

        word_detections, word_styles = cluster_word_styles(word_records)

        mean_confidence = float(np.mean([w["confidence"] for w in word_detections]))

        return {
            "word_detections": word_detections,
            "word_styles": word_styles,
            "word_analysis": {
                "attempted": True,
                "success": True,
                "confidence": round(_clamp(mean_confidence, 0.0, 1.0), 3),
                "word_count": len(word_detections),
                "message": (
                    f"detected {len(word_detections)} tracked word(s), "
                    f"{len(word_styles)} emphasis style(s)"
                ),
            },
        }

    except Exception as exc:
        return {
            "word_detections": [],
            "word_styles": {},
            "word_analysis": {
                "attempted": True,
                "success": False,
                "confidence": 0.0,
                "word_count": 0,
                "message": f"word-level analysis failed internally: {exc}",
            },
        }
