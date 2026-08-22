import argparse
import json
import os
from pathlib import Path

import cv2


def analyze_video(video_path: str) -> dict:
    """Analyze a reference video and create a basic STYLE_PROFILE."""

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

    # Sample representative frames.
    sample_count = min(
        12,
        max(1, frame_count)
    )

    samples = []

    if frame_count > 0:

        if sample_count == 1:
            positions = [0]
        else:
            positions = [
                int(
                    i * (frame_count - 1)
                    / (sample_count - 1)
                )
                for i in range(sample_count)
            ]

        for frame_number in positions:

            cap.set(
                cv2.CAP_PROP_POS_FRAMES,
                frame_number
            )

            success, frame = cap.read()

            if not success:
                continue

            samples.append({
                "frame": frame_number,
                "time_seconds": round(
                    frame_number / fps,
                    3
                ) if fps > 0 else 0,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0])
            })

    cap.release()

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
            "mode": "FAST",
            "sample_count": len(samples),
            "samples": samples
        },

        "caption": {
            "font_family": "",
            "font_weight": 700,
            "size_px": 0,
            "fill": "#FFFFFF",
            "highlight": "#FFFFFF",

            "position": {
                "mode": "reference",
                "x": 0.5,
                "y": 0.5
            },

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
                "color": "#FFFFFF",
                "opacity": 0,
                "radius": 0
            },

            "animation": {
                "type": "none",
                "duration_ms": 0,
                "strength": 0
            }
        },

        "confidence": {
            "video": 1.0,
            "caption": 0.0
        }
    }

    return style_profile


def main():

    parser = argparse.ArgumentParser(
        description="EditIQ reference video analyzer"
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

    args = parser.parse_args()

    profile = analyze_video(
        args.video
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
