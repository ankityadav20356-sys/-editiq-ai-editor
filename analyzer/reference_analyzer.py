import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize(value, maximum):
    if maximum <= 0:
        return 0.0
    return round(float(value) / float(maximum), 4)


def sample_frames(cap, frame_count, fps, sample_count=24):
    if frame_count <= 0:
        return []

    count = min(sample_count, frame_count)

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
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))

        success, frame = cap.read()

        if not success or frame is None:
            continue

        samples.append({
            "frame_number": int(frame_number),
            "time_seconds": round(
                frame_number / fps,
                3
            ) if fps > 0 else 0,
            "frame": frame
        })

    return samples


def detect_bright_caption_region(frame):
    """
    Detect likely caption pixels.

    This is intentionally conservative.
    We look for bright, relatively low-saturation pixels,
    which commonly represent white/silver captions.
    """

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Bright + relatively low saturation.
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, 150], dtype=np.uint8),
        np.array([180, 110, 255], dtype=np.uint8)
    )

    height, width = mask.shape

    # Captions are commonly located in the lower/middle
    # portion of vertical social videos.
    y_start = int(height * 0.35)
    roi = mask[y_start:, :]

    kernel = np.ones((3, 3), np.uint8)

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
        x, y, w, h = cv2.boundingRect(contour)

        y += y_start

        area = w * h

        if area < width * height * 0.00005:
            continue

        if w < width * 0.05:
            continue

        if h > height * 0.25:
            continue

        candidates.append(
            (area, x, y, w, h)
        )

    if not candidates:
        return None

    # Prefer wide horizontal text-like regions.
    candidates.sort(
        key=lambda item: (
            item[3] / max(item[4], 1),
            item[0]
        ),
        reverse=True
    )

    _, x, y, w, h = candidates[0]

    return {
        "x": x,
        "y": y,
        "width": w,
        "height": h
    }


def estimate_caption_color(frame, region):
    if not region:
        return "#FFFFFF", 0.0

    x = region["x"]
    y = region["y"]
    w = region["width"]
    h = region["height"]

    crop = frame[
        y:y + h,
        x:x + w
    ]

    if crop.size == 0:
        return "#FFFFFF", 0.0

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # Bright pixels are more likely to belong to text.
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, 150], dtype=np.uint8),
        np.array([180, 180, 255], dtype=np.uint8)
    )

    pixels = crop[mask > 0]

    if len(pixels) < 10:
        return "#FFFFFF", 0.1

    # Remove very dark/irrelevant pixels.
    mean_bgr = np.mean(
        pixels,
        axis=0
    )

    b, g, r = [
        int(clamp(round(v), 0, 255))
        for v in mean_bgr
    ]

    color = "#{:02X}{:02X}{:02X}".format(
        r,
        g,
        b
    )

    confidence = clamp(
        len(pixels) / max(crop.shape[0] * crop.shape[1], 1),
        0.0,
        1.0
    )

    return color, round(float(confidence), 3)


def estimate_position(region, width, height):
    if not region:
        return {
            "mode": "reference",
            "x": 0.5,
            "y": 0.5,
            "width": 0.0,
            "height": 0.0
        }

    center_x = (
        region["x"] +
        region["width"] / 2
    )

    center_y = (
        region["y"] +
        region["height"] / 2
    )

    return {
        "mode": "reference",
        "x": normalize(center_x, width),
        "y": normalize(center_y, height),
        "width": normalize(region["width"], width),
        "height": normalize(region["height"], height)
    }


def analyze_animation(regions, fps):
    """
    Estimate whether the detected caption region changes
    substantially between sampled frames.

    This is a basic signal, not a full motion-tracking system.
    """

    valid = [
        r for r in regions
        if r is not None
    ]

    if len(valid) < 3:
        return {
            "type": "none",
            "duration_ms": 0,
            "strength": 0.0
        }

    centers = []

    for region in valid:
        centers.append(
            (
                region["x"] + region["width"] / 2,
                region["y"] + region["height"] / 2
            )
        )

    movement = []

    for i in range(1, len(centers)):
        dx = centers[i][0] - centers[i - 1][0]
        dy = centers[i][1] - centers[i - 1][1]

        movement.append(
            float(np.sqrt(dx * dx + dy * dy))
        )

    if not movement:
        return {
            "type": "none",
            "duration_ms": 0,
            "strength": 0.0
        }

    average_movement = float(
        np.mean(movement)
    )

    if average_movement < 8:
        animation_type = "none"
    elif average_movement < 25:
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

    strength = clamp(
        average_movement / 50.0,
        0.0,
        1.0
    )

    return {
        "type": animation_type,
        "duration_ms": duration_ms,
        "strength": round(strength, 3)
    }


def analyze_video(video_path: str, mode="FAST") -> dict:

    if not os.path.isfile(video_path):
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )
    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )
    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    duration = (
        frame_count / fps
        if fps > 0
        else 0
    )

    aspect_ratio = (
        width / height
        if height > 0
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

    regions = []
    colors = []

    frame_metadata = []

    for sample in samples:

        frame = sample["frame"]

        region = detect_bright_caption_region(
            frame
        )

        regions.append(region)

        color, color_confidence = (
            estimate_caption_color(
                frame,
                region
            )
        )

        colors.append(
            (
                color,
                color_confidence
            )
        )

        frame_metadata.append({
            "frame_number": sample[
                "frame_number"
            ],
            "time_seconds": sample[
                "time_seconds"
            ],
            "caption_detected": (
                region is not None
            )
        })

    cap.release()

    valid_regions = [
        region
        for region in regions
        if region is not None
    ]

    if valid_regions:

        average_region = {
            "x": int(
                np.mean([
                    r["x"]
                    for r in valid_regions
                ])
            ),
            "y": int(
                np.mean([
                    r["y"]
                    for r in valid_regions
                ])
            ),
            "width": int(
                np.mean([
                    r["width"]
                    for r in valid_regions
                ])
            ),
            "height": int(
                np.mean([
                    r["height"]
                    for r in valid_regions
                ])
            )
        }

    else:

        average_region = None

    # Most frequently detected color.
    detected_colors = [
        color
        for color, confidence in colors
        if confidence > 0.05
    ]

    if detected_colors:
        unique, counts = np.unique(
            detected_colors,
            return_counts=True
        )

        fill = str(
            unique[
                int(np.argmax(counts))
            ]
        )
    else:
        fill = "#FFFFFF"

    detection_confidence = (
        len(valid_regions) /
        max(len(samples), 1)
    )

    position = estimate_position(
        average_region,
        width,
        height
    )

    animation = analyze_animation(
        regions,
        fps
    )

    style_profile = {

        "version": 2,

        "video": {
            "width": width,
            "height": height,
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_seconds": round(
                duration,
                3
            ),
            "aspect_ratio": round(
                aspect_ratio,
                4
            )
        },

        "analysis": {
            "mode": mode.upper(),
            "sample_count": len(samples),
            "caption_detection_rate": round(
                detection_confidence,
                3
            ),
            "samples": frame_metadata
        },

        "caption": {

            "font_family": "",

            "font_weight": 700,

            "size_px": (
                average_region["height"]
                if average_region
                else 0
            ),

            "fill": fill,

            "highlight": fill,

            "position": position,

            "shadow": {
                "enabled": False,
                "color": "#000000",
                "opacity": 0,
                "offset_x": 0,
                "offset_y": 0,
                "blur": 0
            },

            "stroke": {
                "enabled": False,
                "color": "#000000",
                "width": 0,
                "opacity": 0
            },

            "glow": {
                "enabled": False,
                "color": fill,
                "opacity": 0,
                "radius": 0
            },

            "animation": animation
        },

        "confidence": {

            "video": 1.0,

            "caption": round(
                detection_confidence,
                3
            ),

            "position": round(
                detection_confidence,
                3
            ),

            "color": round(
                detection_confidence,
                3
            )
        }
    }

    return style_profile


def main():

    parser = argparse.ArgumentParser(
        description=(
            "EditIQ V1 reference video analyzer"
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
