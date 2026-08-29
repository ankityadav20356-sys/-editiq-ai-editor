"""CLI: python -m editiq {analyze, transcribe, plan} <media_path>

Usable against real media files. Output is JSON, either printed to stdout
or written with --output.
"""

from __future__ import annotations

import argparse
import json
import sys

from planner.models import PlannerConfig
from transcription.faster_whisper_backend import FasterWhisperBackend
from transcription.mock_backend import MockTranscriptionBackend
from transcription.normalize import normalize_transcript
from transcription.segment import segment_transcript

from .pipeline import analyze_media, run_pipeline


def _build_backend(args):
    if args.backend == "mock":
        return MockTranscriptionBackend()
    return FasterWhisperBackend(model_size=args.model, language=args.language)


def _emit(data: dict, output: str | None) -> None:
    text = json.dumps(data, indent=2)
    if output:
        with open(output, "w") as f:
            f.write(text)
    else:
        print(text)


def cmd_analyze(args) -> int:
    result = analyze_media(args.media)
    _emit(result, args.output)
    return 0


def cmd_transcribe(args) -> int:
    backend = _build_backend(args)
    transcript = backend.transcribe(args.media)
    transcript = normalize_transcript(transcript)
    transcript = segment_transcript(transcript)
    _emit(transcript.to_dict(), args.output)
    return 0


def cmd_plan(args) -> int:
    backend = _build_backend(args)
    project = {"width": args.width, "height": args.height, "fps": args.fps}
    try:
        plan = run_pipeline(args.media, project, backend=backend, planner_config=PlannerConfig())
    except Exception as exc:  # surface validation/backend errors clearly on the CLI
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _emit(plan, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="editiq", description="EditIQ Phase 1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn in (("analyze", cmd_analyze), ("transcribe", cmd_transcribe), ("plan", cmd_plan)):
        p = sub.add_parser(name)
        p.add_argument("media", help="Path to the media file")
        p.add_argument("--output", help="Write JSON output to this path instead of stdout")
        if name in ("transcribe", "plan"):
            p.add_argument("--backend", choices=["mock", "faster-whisper"], default="mock")
            p.add_argument("--model", default="base", help="faster-whisper model size")
            p.add_argument("--language", default=None, help="Force a language code, e.g. en")
        if name == "plan":
            p.add_argument("--width", type=int, default=1080)
            p.add_argument("--height", type=int, default=1920)
            p.add_argument("--fps", type=float, default=30)
        p.set_defaults(func=fn)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
