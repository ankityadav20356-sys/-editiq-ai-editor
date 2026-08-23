"""
Style Profile Engine — the clean, stable interface between a reference
video and a validated STYLE PROFILE.

    REFERENCE VIDEO -> ANALYZER -> STYLE PROFILE JSON -> CAPTION RENDERER

This module does NOT reimplement any visual-analysis logic. All actual
detection (caption region, color, position, effects, animation) lives in
analyzer/reference_analyzer.py, which is left untouched. This module's
only job is to:

  1. Provide a single stable entry point (`StyleProfileEngine.analyze`)
     that other code (CLI, future automation) can depend on without
     knowing about reference_analyzer's internals.
  2. Validate whatever the analyzer produces against
     schemas/style_profile.schema.json before it's trusted anywhere
     downstream, using schemas/validate.py.
  3. Provide load/save helpers that also validate, so a hand-authored
     or edited style profile can't silently drift out of schema.

Word-level / phrase-level style authoring (word_styles / phrase_styles)
is NOT synthesized by this engine or by the analyzer — the analyzer only
detects a single global caption style from the reference video. Per-word
styling is authored data (see tests/fixtures for examples), not something
this foundation infers automatically. That is intentionally out of scope
for this step (see NEXT SINGLE STEP in the project report).
"""

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analyzer.reference_analyzer import analyze_video  # noqa: E402
from schemas.validate import (  # noqa: E402
    DEFAULT_SCHEMA_PATH,
    SchemaValidationError,
    validate_style_profile,
)


class StyleProfileEngine:
    """Thin, validated wrapper around the reference analyzer."""

    def __init__(self, schema_path=DEFAULT_SCHEMA_PATH):
        self.schema_path = schema_path

    def analyze(self, video_path, mode="FAST"):
        """
        Analyze a reference video and return a validated style profile.

        Raises SchemaValidationError if the analyzer's own output doesn't
        conform to the schema (a regression signal — the analyzer and
        schema should never drift apart silently).
        """
        profile = analyze_video(video_path, mode)
        validate_style_profile(profile, self.schema_path)
        return profile

    def load_profile(self, path):
        """Load a style profile from disk and validate it."""
        with open(path, "r", encoding="utf-8") as file:
            profile = json.load(file)
        validate_style_profile(profile, self.schema_path)
        return profile

    def save_profile(self, profile, path):
        """Validate a style profile, then write it to disk."""
        validate_style_profile(profile, self.schema_path)
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(profile, file, indent=2, ensure_ascii=False)
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a reference video into a validated STYLE_PROFILE."
    )
    parser.add_argument("video", help="Path to reference video")
    parser.add_argument(
        "--output", default="style_profile.json", help="Output STYLE_PROFILE JSON"
    )
    parser.add_argument(
        "--mode", choices=["FAST", "QUALITY"], default="FAST", help="Analysis quality"
    )
    args = parser.parse_args()

    engine = StyleProfileEngine()

    try:
        profile = engine.analyze(args.video, args.mode)
    except SchemaValidationError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

    output_path = engine.save_profile(profile, args.output)
    print(f"EditIQ: validated STYLE_PROFILE created → {output_path}")


if __name__ == "__main__":
    main()
