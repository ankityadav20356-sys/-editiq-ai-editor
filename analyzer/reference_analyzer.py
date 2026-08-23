import argparse
import json
import os
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize(value, maximum):
    if maximum <= 0:
        return 0.0

    return round(
        float(value) / float(maximum),
        4
    )


def sample_frames(
    cap,
    frame_count,
    fps,
    sample_count=24
):
    if frame_count <= 0:
        return []

    count = min(
        sample_count,
        frame_count
    )

    if count == 1:
        positions = [0]
    else:
        positions = np.linspace(
            0,
            frame_count - 1,
            count,
            dtype=int
        )

    samples = []

    for frame_number in positions:

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            int(frame_number)
        )

        success, frame = cap.read()

        if not success or frame is None:
            continue

        samples.append(
            {
                "frame_number": int(
                    frame_number
                ),
                "time_seconds": round(
                    frame_number / fps,
                    3
                ) if fps > 0 else 0,
                "frame": frame
            }
        )

    return samples


def detect_caption_region(frame):
    """
    Detect bright, text-like caption regions.

    This is a visual-estimation stage.
    Exact font identification is intentionally
    left for a future OCR/font-matching module.
    """

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )

    mask = cv2.inRange(
        hsv,
        np.array(
            [0, 0, 150],
            dtype=np.uint8
        ),
        np.array(
            [180, 120, 255],
            dtype=np.uint8
        )
    )

    height, width = mask.shape

    # Ignore the top area where UI/background
    # elements are more likely to create noise.
    y_start = int(
        height * 0.30
    )

    roi = mask[
        y_start:,
        :
    ]

    kernel = np.ones(
        (3, 3),
        np.uint8
    )

    roi = cv2.morphologyEx(
        roi,
        cv2.MORPH_OPEN,
        kernel
    )

    roi = cv2.morphologyEx(
        roi,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        roi,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []

    for contour in contours:

        x, y, w, h = cv2.boundingRect(
            contour
        )

        y += y_start

        area = w * h

        if area < width * height * 0.00005:
            continue

        if w < width * 0.04:
            continue

        if h > height * 0.20:
            continue

        aspect_ratio = (
            w / max(h, 1)
        )

        if aspect_ratio < 1.2:
            continue

        candidates.append(
            {
                "area": area,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "aspect_ratio": aspect_ratio
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item["aspect_ratio"],
            item["area"]
        ),
        reverse=True
    )

    best = candidates[0]

    return {
        "x": best["x"],
        "y": best["y"],
        "width": best["width"],
        "height": best["height"]
    }


def estimate_caption_color(
    frame,
    region
):
    if not region:
        return "#FFFFFF", 0.0

    x = region["x"]
    y = region["y"]
    width = region["width"]
    height = region["height"]

    crop = frame[
        y:y + height,
        x:x + width
    ]

    if crop.size == 0:
        return "#FFFFFF", 0.0

    hsv = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2HSV
    )

    bright_mask = cv2.inRange(
        hsv,
        np.array(
            [0, 0, 150],
            dtype=np.uint8
        ),
        np.array(
            [180, 180, 255],
            dtype=np.uint8
        )
    )

    pixels = crop[
        bright_mask > 0
    ]

    if len(pixels) < 10:
        return "#FFFFFF", 0.05

    mean_bgr = np.mean(
        pixels,
        axis=0
    )

    b, g, r = [
        int(
            clamp(
                round(value),
                0,
                255
            )
        )
        for value in mean_bgr
    ]

    color = (
        "#{:02X}{:02X}{:02X}"
        .format(
            r,
            g,
            b
        )
    )

    confidence = clamp(
        len(pixels)
        /
        max(
            crop.shape[0]
            * crop.shape[1],
            1
        ),
        0.0,
        1.0
    )

    return (
        color,
        round(
            float(confidence),
            3
        )
    )


def estimate_position(
    region,
    width,
    height
):
    if not region:
        return {
            "x": 0.5,
            "y": 0.55
        }

    center_x = (
        region["x"]
        +
        region["width"] / 2
    )

    center_y = (
        region["y"]
        +
        region["height"] / 2
    )

    return {
        "x": normalize(
            center_x,
            width
        ),
        "y": normalize(
            center_y,
            height
        )
    }


def estimate_alignment(
    region,
    frame_width
):
    if not region:
        return "center"

    center_x = (
        region["x"]
        +
        region["width"] / 2
    )

    normalized = (
        center_x
        /
        max(frame_width, 1)
    )

    if normalized < 0.38:
        return "left"

    if normalized > 0.62:
        return "right"

    return "center"


def estimate_font_size(
    region
):
    if not region:
        return 56

    text_height = max(
        region["height"],
        1
    )

    # Approximate caption size from
    # detected pixel height.
    estimated = (
        text_height * 1.65
    )

    return round(
        clamp(
            estimated,
            20,
            180
        ),
        1
    )


def estimate_word_capacity(
    region,
    frame_width
):
    if not region:
        return 7

    width_ratio = (
        region["width"]
        /
        max(frame_width, 1)
    )

    if width_ratio < 0.30:
        return 4

    if width_ratio < 0.50:
        return 6

    if width_ratio < 0.70:
        return 8

    return 10


def estimate_effects(
    frame,
    region,
    fill_color
):
    """
    Estimate stroke/shadow/glow conservatively.

    We only enable an effect when the pixels around
    the detected text region provide some evidence.
    """

    result = {
        "stroke": {
            "enabled": False,
            "width_px": 0,
            "color": "#000000",
            "opacity": 0.0
        },
        "shadow": {
            "enabled": False,
            "opacity": 0.0,
            "blur_px": 0.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "color": "#000000"
        },
        "glow": {
            "enabled": False,
            "blur_px": 0.0,
            "opacity": 0.0,
            "color": fill_color
        }
    }

    if not region:
        return result

    x = region["x"]
    y = region["y"]
    width = region["width"]
    height = region["height"]

    padding = max(
        4,
        int(
            min(
                width,
                height
            ) * 0.12
        )
    )

    x1 = max(
        0,
        x - padding
    )

    y1 = max(
        0,
        y - padding
    )

    x2 = min(
        frame.shape[1],
        x + width + padding
    )

    y2 = min(
        frame.shape[0],
        y + height + padding
    )

    expanded = frame[
        y1:y2,
        x1:x2
    ]

    if expanded.size == 0:
        return result

    hsv = cv2.cvtColor(
        expanded,
        cv2.COLOR_BGR2HSV
    )

    # Strong low-saturation bright areas are usually
    # the actual caption body.
    bright = cv2.inRange(
        hsv,
        np.array(
            [0, 0, 175],
            dtype=np.uint8
        ),
        np.array(
            [180, 100, 255],
            dtype=np.uint8
        )
    )

    caption_ratio = (
        np.count_nonzero(bright)
        /
        max(
            bright.shape[0]
            * bright.shape[1],
            1
        )
    )

    # Very rough evidence for an outline/shadow
    # around bright text.
    dark = cv2.inRange(
        hsv,
        np.array(
            [0, 0, 0],
            dtype=np.uint8
        ),
        np.array(
            [180, 255, 90],
            dtype=np.uint8
        )
    )

    dark_ratio = (
        np.count_nonzero(dark)
        /
        max(
            dark.shape[0]
            * dark.shape[1],
            1
        )
    )

    if (
        caption_ratio > 0.01
        and dark_ratio > 0.20
    ):
        result["stroke"] = {
            "enabled": True,
            "width_px": 1.5,
            "color": "#000000",
            "opacity": 0.55
        }

    if (
        caption_ratio > 0.01
        and dark_ratio > 0.35
    ):
        result["shadow"] = {
            "enabled": True,
            "opacity": 0.35,
            "blur_px": 2,
            "offset_x": 2,
            "offset_y": 2,
            "color": "#000000"
        }

    return result


def analyze_animation(
    regions,
    fps
):
    valid = [
        region
        for region in regions
        if region is not None
    ]

    if len(valid) < 3:
        return {
            "type": "none",
            "duration_ms": 0,
            "easing": "linear",
            "intensity": 0.0
        }

    centers = []

    for region in valid:
        centers.append(
            (
                region["x"]
                +
                region["width"] / 2,
                region["y"]
                +
                region["height"] / 2
            )
        )

    movement = []

    for index in range(
        1,
        len(centers)
    ):
        dx = (
            centers[index][0]
            -
            centers[index - 1][0]
        )

        dy = (
            centers[index][1]
            -
            centers[index - 1][1]
        )

        movement.append(
            float(
                np.sqrt(
                    dx * dx
                    +
                    dy * dy
                )
            )
        )

    if not movement:
        return {
            "type": "none",
            "duration_ms": 0,
            "easing": "linear",
            "intensity": 0.0
        }

    average_movement = float(
        np.mean(movement)
    )

    if average_movement < 5:
        animation_type = "none"
    elif average_movement < 15:
        animation_type = "subtle_motion"
    else:
        animation_type = "motion"

    duration_ms = (
        round(
            1000 / fps,
            1
        )
        if fps > 0
        else 0
    )

    intensity = clamp(
        average_movement / 50.0,
        0.0,
        1.0
    )

    return {
        "type": animation_type,
        "duration_ms": duration_ms,
        "easing": "linear",
        "intensity": round(
            float(intensity),
            3
        )
    }


def analyze_video(
    video_path: str,
    mode="FAST"
):
    if not os.path.isfile(
        video_path
    ):
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    cap = cv2.VideoCapture(
        video_path
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video: {video_path}"
        )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    frame_count = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    duration = (
        frame_count / fps
        if fps > 0
        else 0
    )

    sample_count = (
        24
        if mode.upper() == "QUALITY"
        else 12
    )

    samples = sample_frames(
        cap,
        frame_count,
        fps,
        sample_count
    )

    cap.release()

    regions = []
    detected_colors = []
    color_confidences = []

    for sample in samples:

        frame = sample["frame"]

        region = detect_caption_region(
            frame
        )

        regions.append(
            region
        )

        color, confidence = (
            estimate_caption_color(
                frame,
                region
            )
        )

        if confidence >= 0.05:
            detected_colors.append(
                color
            )

        color_confidences.append(
            confidence
        )

    valid_regions = [
        region
        for region in regions
        if region is not None
    ]

    if valid_regions:

        average_region = {
            "x": int(
                np.mean(
                    [
                        region["x"]
                        for region in valid_regions
                    ]
                )
            ),
            "y": int(
                np.mean(
                    [
                        region["y"]
                        for region in valid_regions
                    ]
                )
            ),
            "width": int(
                np.mean(
                    [
                        region["width"]
                        for region in valid_regions
                    ]
                )
            ),
            "height": int(
                np.mean(
                    [
                        region["height"]
                        for region in valid_regions
                    ]
                )
            )
        }

    else:
        average_region = None

    if detected_colors:
        fill = Counter(
            detected_colors
        ).most_common(1)[0][0]
    else:
        fill = "#FFFFFF"

    detection_rate = (
        len(valid_regions)
        /
        max(
            len(samples),
            1
        )
    )

    mean_color_confidence = (
        float(
            np.mean(
                color_confidences
            )
        )
        if color_confidences
        else 0.0
    )

    caption_confidence = clamp(
        (
            detection_rate * 0.70
            +
            mean_color_confidence * 0.30
        ),
        0.0,
        1.0
    )

    position = estimate_position(
        average_region,
        width,
        height
    )

    alignment = estimate_alignment(
        average_region,
        width
    )

    font_size = estimate_font_size(
        average_region
    )

    max_words = estimate_word_capacity(
        average_region,
        width
    )

    effects = (
        estimate_effects(
            samples[0]["frame"],
            average_region,
            fill
        )
        if samples and average_region
        else {
            "stroke": {
                "enabled": False,
                "width_px": 0,
                "color": "#000000",
                "opacity": 0.0
            },
            "shadow": {
                "enabled": False,
                "opacity": 0.0,
                "blur_px": 0.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "color": "#000000"
            },
            "glow": {
                "enabled": False,
                "blur_px": 0.0,
                "opacity": 0.0,
                "color": fill
            }
        }
    )

    animation = analyze_animation(
        regions,
        fps
    )

    # Use normalized position as the
    # reference location, while margins
    # remain compatible with the renderer.
    margin_left = round(
        position["x"] * width
    )

    margin_right = round(
        width
        -
        position["x"] * width
    )

    margin_vertical = round(
        height
        -
        position["y"] * height
    )

    style_profile = {
        "style_id": "reference_caption_style",
        "version": 2,
        "confidence": round(
            caption_confidence,
            3
        ),
        "caption": {
            "font_family": "",
            "font_weight": 700,
            "size_px": font_size,
            "fill": fill,
            "highlight": fill,
            "opacity": 1.0,
            "letter_spacing": 0,
            "line_height": 1.0,
            "alignment": alignment,
            "max_words_per_line": max_words,
            "margin_left": margin_left,
            "margin_right": margin_right,
            "margin_vertical": margin_vertical,
            "position": {
                "x": margin_left,
                "y": margin_vertical
            },
            "safe_area": {
                "top": 120,
                "bottom": 160,
                "left": 80,
                "right": 80
            },
            "stroke": effects["stroke"],
            "shadow": effects["shadow"],
            "glow": effects["glow"],
            "animation": animation
        },
        "color": {
            "exposure": 0,
            "contrast": 0,
            "saturation": 0,
            "temperature": 0,
            "tint": 0
        },
        "audio": {
            "noise_reduction": False,
            "eq": False,
            "compression": False,
            "loudness_target_lufs": -14
        },
        "motion": {
            "default_transition": "none",
            "default_easing": animation["easing"],
            "default_zoom_strength": 0
        }
    }

    return style_profile


def main():

    parser = argparse.ArgumentParser(
        description=(
            "EditIQ reference caption "
            "style analyzer V2"
        )
    )

    parser.add_argument(
        "video",
        help="Path to reference video"
    )

    parser.add_argument(
        "--output",
        default="style_profile.json",
        help="Output STYLE_PROFILE JSON"
    )

    parser.add_argument(
        "--mode",
        choices=[
            "FAST",
            "QUALITY"
        ],
        default="FAST",
        help="Analysis quality"
    )

    args = parser.parse_args()

    profile = analyze_video(
        args.video,
        args.mode
    )

    output_path = Path(
        args.output
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            profile,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        "EditIQ: STYLE_PROFILE created → "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
