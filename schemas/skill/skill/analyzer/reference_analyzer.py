import argparse
import json
import os
from pathlib import Path

import cv2


def analyze_video(video_path: str) -> dict:
    """
    Analyze basic technical properties of a reference video.

    This is V1 of the analyzer.
    Caption-specific visual analysis will be added in later iterations.
    """

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    duration = frame_count / fps if fps else 0

    sample_count = min(12, max(1, frame_count))
    sample_frames = []

    if frame_count > 0:
        positions = [
            int(i * (frame_count - 1) / max(1, sample_count - 1))
            for i in range(sample_count)
        ]

        for frame_number in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            success, frame = cap.read()

            if not success:
                continue

            sample_frames.append({
                "frame": frame_number,
                "time": round(frame_number / fps, 3) if fps else 0,
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0])
            })

    cap.release()

    aspect_ratio = round(width / height, 4) if height else 0

    return {
        "style_id": Path(video_path).stem,
        "version": 1,
        "confidence": 0.0,
        "video": {
            "path": video_path,
            "width": width,
            "height": height,
            "fps": round(fps, 3) if fps else 0,
            "frame_count": frame_count,
            "duration_seconds": round(duration, 3),
            "aspect_ratio": aspect_ratio
        },
        "analysis": {
            "mode": "FAST",
            "sample_count": len(sample_frames),
            "samples": sample_frames
        },
        "caption": {},
        "color": {},
        "audio": {},
        "motion": {}
    }


def main():
    parser = argparse.ArgumentParser(
        description="EditIQ V1 reference video analyzer"
    )

    parser.add_argument(
        "video",
        help="Path to the reference video"
    )

    parser.add_argument(
        "--output",
        default="style_profile.json",
        help="Output JSON file"
    )

    args = parser.parse_args()

    profile = analyze_video(args.video)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(profile, file, indent=2, ensure_ascii=False)

    print(f"EditIQ: Style profile created → {output_path}")


if __name__ == "__main__":
    main()
