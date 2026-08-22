import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def hex_to_ass_color(color):
    color = color.lstrip("#")

    if len(color) != 6:
        color = "FFFFFF"

    r = color[0:2]
    g = color[2:4]
    b = color[4:6]

    return f"&H00{b}{g}{r}"


def seconds_to_ass(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60

    return (
        f"{hours}:"
        f"{minutes:02d}:"
        f"{remaining:05.2f}"
    )


def create_ass_style(style):
    caption = style.get("caption", {})

    font = caption.get(
        "font_family",
        "Arial"
    )

    size = caption.get(
        "size_px",
        56
    )

    weight = caption.get(
        "font_weight",
        700
    )

    fill = hex_to_ass_color(
        caption.get(
            "fill",
            "#FFFFFF"
        )
    )

    highlight = hex_to_ass_color(
        caption.get(
            "highlight",
            "#FFFFFF"
        )
    )

    shadow = caption.get(
        "shadow",
        {}
    )

    stroke = caption.get(
        "stroke",
        {}
    )

    shadow_enabled = shadow.get(
        "enabled",
        False
    )

    stroke_enabled = stroke.get(
        "enabled",
        False
    )

    outline = (
        stroke.get("width", 0)
        if stroke_enabled
        else 0
    )

    shadow_size = (
        2
        if shadow_enabled
        else 0
    )

    bold = -1 if weight >= 600 else 0

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EditIQ,{font},{size},{fill},{highlight},&H00000000,&H80000000,{bold},0,0,0,100,100,0,0,1,{outline},{shadow_size},5,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_events(captions):
    events = []

    for caption in captions:

        start = seconds_to_ass(
            float(caption["start"])
        )

        end = seconds_to_ass(
            float(caption["end"])
        )

        text = caption.get(
            "text",
            ""
        ).strip()

        if not text:
            continue

        text = text.replace(
            "\n",
            r"\N"
        )

        events.append(
            "Dialogue: "
            f"0,{start},{end},EditIQ,"
            ",0,0,0,,"
            f"{text}"
        )

    return "\n".join(events)


def create_ass_file(
    style_profile,
    captions,
    output_path
):

    ass_content = create_ass_style(
        style_profile
    )

    ass_content += build_events(
        captions
    )

    Path(output_path).write_text(
        ass_content,
        encoding="utf-8"
    )


def render_video(
    input_video,
    output_video,
    style_profile_path,
    captions_path
):

    if not os.path.isfile(input_video):
        raise FileNotFoundError(
            input_video
        )

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

    with tempfile.TemporaryDirectory() as temp:

        ass_path = Path(temp) / "captions.ass"

        create_ass_file(
            style_profile,
            captions,
            ass_path
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
        "EditIQ: Render complete → "
        f"{output_video}"
    )


def main():

    parser = argparse.ArgumentParser(
        description="EditIQ caption renderer"
    )

    parser.add_argument(
        "--input",
        required=True
    )

    parser.add_argument(
        "--style",
        required=True
    )

    parser.add_argument(
        "--captions",
        required=True
    )

    parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    render_video(
        input_video=args.input,
        output_video=args.output,
        style_profile_path=args.style,
        captions_path=args.captions
    )


if __name__ == "__main__":
    main()
