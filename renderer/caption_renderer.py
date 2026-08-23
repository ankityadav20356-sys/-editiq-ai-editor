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

    return f"{hours}:{minutes:02d}:{remaining:05.2f}"


def get_caption_style(style):
    caption = style.get("caption", {})

    return {
        "font": caption.get("font_family", "Arial"),
        "size": caption.get("size_px", 56),
        "weight": caption.get("font_weight", 700),
        "fill": caption.get("fill", "#FFFFFF"),
        "highlight": caption.get("highlight", "#FFFFFF"),
        "opacity": caption.get("opacity", 100),
        "spacing": caption.get("letter_spacing", 0),
        "alignment": caption.get("alignment", 5),
        "margin_left": caption.get("margin_left", 80),
        "margin_right": caption.get("margin_right", 80),
        "margin_vertical": caption.get("margin_vertical", 80),
        "stroke": caption.get("stroke", {}),
        "shadow": caption.get("shadow", {}),
        "glow": caption.get("glow", {}),
    }


def create_ass_style(style):
    caption = get_caption_style(style)

    font = caption["font"]
    size = caption["size"]
    weight = caption["weight"]

    fill = hex_to_ass_color(caption["fill"])
    highlight = hex_to_ass_color(caption["highlight"])

    stroke = caption["stroke"]
    shadow = caption["shadow"]

    stroke_enabled = stroke.get("enabled", False)
    shadow_enabled = shadow.get("enabled", False)

    outline = (
        stroke.get("width", 0)
        if stroke_enabled
        else 0
    )

    shadow_size = (
        shadow.get("size", 2)
        if shadow_enabled
        else 0
    )

    bold = -1 if weight >= 600 else 0

    alignment = caption["alignment"]

    margin_left = caption["margin_left"]
    margin_right = caption["margin_right"]
    margin_vertical = caption["margin_vertical"]

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EditIQ,{font},{size},{fill},{highlight},&H00000000,&H80000000,{bold},0,0,0,100,100,{caption["spacing"]},0,1,{outline},{shadow_size},{alignment},{margin_left},{margin_right},{margin_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def escape_ass_text(text):
    text = text.replace("\\", r"\\")
    text = text.replace("{", r"\{")
    text = text.replace("}", r"\}")
    text = text.replace("\n", r"\N")

    return text


def build_events(captions, style):
    events = []

    caption_style = get_caption_style(style)

    primary_color = hex_to_ass_color(
        caption_style["fill"]
    )

    highlight_color = hex_to_ass_color(
        caption_style["highlight"]
    )

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

        words = caption.get("words")

        if words:
            rendered_words = []

            for word in words:

                word_text = escape_ass_text(
                    str(word.get("text", ""))
                )

                highlighted = word.get(
                    "highlight",
                    False
                )

                if highlighted:
                    rendered_words.append(
                        "{\\c" +
                        highlight_color +
                        "}" +
                        word_text +
                        "{\\c" +
                        primary_color +
                        "}"
                    )
                else:
                    rendered_words.append(
                        word_text
                    )

            text = " ".join(rendered_words)

        else:
            text = escape_ass_text(text)

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
        captions,
        style_profile
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
        "EditIQ: Caption render complete → "
        f"{output_video}"
    )


def main():

    parser = argparse.ArgumentParser(
        description="EditIQ deterministic caption renderer"
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
