import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def hex_to_ass_color(color, alpha=0):
    color = str(color or "#FFFFFF").lstrip("#")

    if len(color) != 6:
        color = "FFFFFF"

    r = color[0:2]
    g = color[2:4]
    b = color[4:6]

    alpha = max(0, min(255, int(alpha)))

    return f"&H{alpha:02X}{b}{g}{r}"


def seconds_to_ass(seconds):
    seconds = max(0, float(seconds))

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60

    return f"{hours}:{minutes:02d}:{remaining:05.2f}"


def alignment_to_ass(alignment):
    mapping = {
        "left": 4,
        "center": 5,
        "right": 6
    }

    return mapping.get(
        str(alignment).lower(),
        5
    )


def load_caption_style(style):
    caption = style.get("caption", {})

    return {
        "font_family": caption.get(
            "font_family",
            "Arial"
        ),
        "font_weight": caption.get(
            "font_weight",
            700
        ),
        "size_px": caption.get(
            "size_px",
            56
        ),
        "fill": caption.get(
            "fill",
            "#FFFFFF"
        ),
        "highlight": caption.get(
            "highlight",
            "#FFFFFF"
        ),
        "opacity": caption.get(
            "opacity",
            1
        ),
        "letter_spacing": caption.get(
            "letter_spacing",
            0
        ),
        "line_height": caption.get(
            "line_height",
            1.0
        ),
        "alignment": caption.get(
            "alignment",
            "center"
        ),
        "max_words_per_line": caption.get(
            "max_words_per_line",
            7
        ),
        "margin_left": caption.get(
            "margin_left",
            80
        ),
        "margin_right": caption.get(
            "margin_right",
            80
        ),
        "margin_vertical": caption.get(
            "margin_vertical",
            120
        ),
        "position": caption.get(
            "position",
            {}
        ),
        "safe_area": caption.get(
            "safe_area",
            {}
        ),
        "stroke": caption.get(
            "stroke",
            {}
        ),
        "shadow": caption.get(
            "shadow",
            {}
        ),
        "glow": caption.get(
            "glow",
            {}
        ),
        "animation": caption.get(
            "animation",
            {}
        )
    }


def create_ass_header(style):
    caption = load_caption_style(style)

    font = caption["font_family"]
    size = caption["size_px"]
    weight = caption["font_weight"]

    opacity = caption["opacity"]

    alpha = int(
        (1 - max(0, min(1, opacity))) * 255
    )

    primary = hex_to_ass_color(
        caption["fill"],
        alpha
    )

    highlight = hex_to_ass_color(
        caption["highlight"],
        alpha
    )

    stroke = caption["stroke"]

    stroke_enabled = stroke.get(
        "enabled",
        False
    )

    stroke_width = (
        stroke.get("width_px", 0)
        if stroke_enabled
        else 0
    )

    stroke_color = hex_to_ass_color(
        stroke.get(
            "color",
            "#000000"
        ),
        int(
            (
                1 -
                stroke.get(
                    "opacity",
                    1
                )
            ) * 255
        )
    )

    shadow = caption["shadow"]

    shadow_enabled = shadow.get(
        "enabled",
        False
    )

    shadow_size = (
        max(
            abs(
                shadow.get(
                    "offset_x",
                    0
                )
            ),
            abs(
                shadow.get(
                    "offset_y",
                    0
                )
            )
        )
        if shadow_enabled
        else 0
    )

    alignment = alignment_to_ass(
        caption["alignment"]
    )

    position = caption["position"]

    margin_left = int(
        position.get(
            "x",
            caption["margin_left"]
        )
    )

    margin_right = int(
        caption["margin_right"]
    )

    margin_vertical = int(
        position.get(
            "y",
            caption["margin_vertical"]
        )
    )

    bold = -1 if weight >= 600 else 0

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EditIQ,{font},{size},{primary},{highlight},{stroke_color},&H80000000,{bold},0,0,0,100,100,{caption["letter_spacing"]},0,1,{stroke_width},{shadow_size},{alignment},{margin_left},{margin_right},{margin_vertical},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def escape_ass_text(text):
    text = str(text)

    text = text.replace(
        "\\",
        r"\\"
    )

    text = text.replace(
        "{",
        r"\{"
    )

    text = text.replace(
        "}",
        r"\}"
    )

    text = text.replace(
        "\n",
        r"\N"
    )

    return text


def word_override_color(color):
    return "\\c" + hex_to_ass_color(
        color,
        0
    )


def build_word_text(words, style):
    caption = load_caption_style(style)

    normal_color = word_override_color(
        caption["fill"]
    )

    highlight_color = word_override_color(
        caption["highlight"]
    )

    rendered = []

    for word in words:
        text = escape_ass_text(
            word.get(
                "text",
                ""
            )
        )

        if not text:
            continue

        highlighted = bool(
            word.get(
                "highlight",
                False
            )
        )

        if highlighted:
            rendered.append(
                "{"
                + highlight_color
                + "}"
                + text
                + "{"
                + normal_color
                + "}"
            )
        else:
            rendered.append(
                text
            )

    return " ".join(rendered)


def build_events(captions, style):
    events = []

    for caption in captions:

        start = float(
            caption.get(
                "start",
                0
            )
        )

        end = float(
            caption.get(
                "end",
                start
            )
        )

        if end <= start:
            continue

        words = caption.get(
            "words"
        )

        if isinstance(
            words,
            list
        ) and words:

            text = build_word_text(
                words,
                style
            )

        else:

            text = escape_ass_text(
                caption.get(
                    "text",
                    ""
                ).strip()
            )

        if not text:
            continue

        events.append(
            "Dialogue: "
            f"0,"
            f"{seconds_to_ass(start)},"
            f"{seconds_to_ass(end)},"
            "EditIQ,"
            ",0,0,0,,"
            f"{text}"
        )

    return "\n".join(events)


def create_ass_file(
    style_profile,
    captions,
    output_path
):

    content = create_ass_header(
        style_profile
    )

    content += build_events(
        captions,
        style_profile
    )

    Path(
        output_path
    ).write_text(
        content,
        encoding="utf-8"
    )


def render_video(
    input_video,
    output_video,
    style_profile_path,
    captions_path
):

    if not os.path.isfile(
        input_video
    ):
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

        ass_path = (
            Path(temp)
            / "captions.ass"
        )

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
        description=(
            "EditIQ deterministic "
            "caption renderer V2"
        )
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
