import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def hex_to_ass_color(hex_color: str) -> str:
    """
    Convert #RRGGBB to ASS BGR format.
    """
    value = hex_color.lstrip("#")

    if len(value) != 6:
        return "&H00FFFFFF"

    r = value[0:2]
    g = value[2:4]
    b = value[4:6]

    return f"&H00{b}{g}{r}"


def create_ass_style(style_profile: dict) -> str:
    caption = style_profile.get("caption", {})

    font = caption.get("font_family", "Arial")
    size = caption.get("size_px", 56)
    weight = caption.get("font_weight", 700)

    fill = hex_to_ass_color(
        caption.get("fill", "#FFFFFF")
    )

    highlight = hex_to_ass_color(
        caption.get("highlight", "#FFFFFF")
    )

    alignment_name = caption.get("alignment", "center")

    alignment_map = {
        "left": 4,
        "center": 5,
        "right": 6
    }

    alignment = alignment_map.get(
        alignment_name,
        5
    )

    bold = -1 if weight >= 600 else 0

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{fill},{highlight},&H00000000,&H00000000,{bold},0,0,0,100,100,0,0,1,0,0,{alignment},80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def seconds_to_ass(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def build_events(captions: list) -> str:
    events = []

    for caption in captions:
        start = seconds_to_ass(
            float(caption["start"])
        )

        end = seconds_to_ass(
            float(caption["end"])
        )

        text = caption.get("text", "").strip()

        if not text:
            continue

        text = text.replace(
            "\n",
            r"\N"
        )

        events.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
        )

    return "\n".join(events)


def render_captions(
    input_video: str,
    output_video: str,
    style_profile_path: str,
    captions_path: str
):
    if not os.path.isfile(input_video):
        raise FileNotFoundError(input_video)

    if not os.path.isfile(style_profile_path):
        raise FileNotFoundError(style_profile_path)

    if not os.path.isfile(captions_path):
        raise FileNotFoundError(captions_path)

    style_profile = load_json(
        style_profile_path
    )

    captions_data = load_json(
        captions_path
    )

    captions = captions_data.get(
        "captions",
        []
    )

    ass_content = create_ass_style(
        style_profile
    )

    ass_content += build_events(
        captions
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        ass_path = Path(temp_dir) / "captions.ass"

        ass_path.write_text(
            ass_content,
            encoding="utf-8"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            input_video,
            "-vf",
            f"ass={ass_path}",
            "-c:a",
            "copy",
            output_video
        ]

        subprocess.run(
            command,
            check=True
        )

    print(
        f"EditIQ: Caption render complete → {output_video}"
    )


def main():

    parser = argparse.ArgumentParser(
        description="EditIQ V1 caption renderer"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Target video"
    )

    parser.add_argument(
        "--style",
        required=True,
        help="STYLE_PROFILE JSON"
    )

    parser.add_argument(
        "--captions",
        required=True,
        help="Caption events JSON"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output video"
    )

    args = parser.parse_args()

    render_captions(
        input_video=args.input,
        output_video=args.output,
        style_profile_path=args.style,
        captions_path=args.captions
    )


if __name__ == "__main__":
    main()
