# EditIQ AI Editor

AI-powered deterministic video editing automation.

## What this is (and isn't)

EditIQ analyzes a talking-head/source video and produces a structured,
validated **edit plan** (JSON) describing captions, cuts, emphasis
moments, restrained zooms, and b-roll suggestions. It does **not** render
video, download stock footage, or make creative judgment calls beyond
deterministic, explainable rules.

Two systems currently coexist in this repo:

1. **Style-profile / reference-analysis system** (pre-existing): OCR-based
   analysis of a reference video's caption styling (`analyzer/`,
   `renderer/caption_renderer.py`, `schemas/style_profile.schema.json`).
   This is unchanged by Phase 1.
2. **Phase 1 autonomous edit-planning pipeline** (this document's main
   subject): transcribe -> normalize -> segment -> plan -> validate,
   producing an *operations*-based edit plan.

## Phase 1 architecture

```
media
  |
  v
analyze (editiq/pipeline.py: analyze_media)     -- ffprobe duration, currently minimal
  |
  v
transcribe (transcription/*)                    -- Faster-Whisper or Mock backend
  |
  v
normalize (transcription/normalize.py)          -- conservative cleanup, no LLM
  |
  v
segment (transcription/segment.py)               -- punctuation/pause/duration/word-count
  |
  v
plan (planner/*)                                 -- deterministic rules -> operations
  |
  v
validate (schemas/edit_plan_validate.py)         -- JSON Schema + semantic checks
  |
  v
edit_plan.json
```

## Directory structure (Phase 1 additions)

```
transcription/
  models.py               Word, Segment, Transcript dataclasses
  backend.py               TranscriptionBackend protocol
  faster_whisper_backend.py  Real backend (lazy-imports faster-whisper)
  mock_backend.py           Deterministic backend for tests/CI
  normalize.py              Conservative text normalization
  segment.py                 Deterministic re-segmentation

planner/
  models.py                 PlannerConfig
  rules.py                   silence cuts, captions, emphasis, zoom, b-roll suggestions
  generator.py               Orchestrates rules -> operations -> edit plan dict

editiq/
  pipeline.py                run_pipeline(): the full orchestration
  cli.py                      analyze / transcribe / plan commands
  __main__.py                 `python -m editiq ...` entry point

schemas/
  edit_plan.schema.json      Extended ADDITIVELY: existing module-toggle
                              fields (`modules`, `caption`, `color`, `audio`,
                              `motion`, `broll`) are untouched. New optional
                              fields: `source`, `segments`, `operations`,
                              `metadata`.
  edit_plan_validate.py      New file (does not modify validate.py):
                              JSON-Schema + semantic validation for the
                              operations-based plan (timestamps, per-type
                              required fields, overlap rules).
```

## Transcription backends

- **`transcription.mock_backend.MockTranscriptionBackend`** -- deterministic,
  no ML model, no network. Used by all unit tests and safe for CI. Returns
  the same transcript for the same configured script every time.
- **`transcription.faster_whisper_backend.FasterWhisperBackend`** -- wraps
  the real `faster-whisper` package with word-level timestamps. Imports
  `faster_whisper` lazily, so simply importing `transcription` never fails
  in an environment without it installed -- only instantiating this class
  does.

### Faster-Whisper setup

```
pip install faster-whisper
```

First use downloads the chosen model (e.g. `tiny`, `base`, `small`) from
Hugging Face Hub. Example:

```python
from transcription.faster_whisper_backend import FasterWhisperBackend
backend = FasterWhisperBackend(model_size="base", device="cpu", compute_type="int8")
transcript = backend.transcribe("video.mp4")
```

## Normalization

`transcription/normalize.py` is deliberately conservative: it collapses
whitespace and drops immediate (near-zero-gap) duplicate words that are
ASR stutter artifacts, while leaving genuinely repeated words (with a
meaningful pause) intact. It never rewrites, translates, or invents
content, and never touches timestamps beyond dropping the dropped word's
own timing.

## Segmentation

`transcription/segment.py` re-groups words into segments using, in order:
sentence-ending punctuation, a configurable pause threshold, a max
duration, and a max word count -- whichever triggers first ends the
current segment. Thresholds are configurable via `SegmentationConfig`.

## Edit-plan generation

`planner/rules.py` implements five deterministic rules:

- **Silence cuts** -- gaps between transcript segments longer than
  `min_silence_s` become suggested `cut` operations.
- **Captions** -- one `caption` operation per (post-segmentation)
  transcript segment.
- **Emphasis** -- at most N words per segment are flagged, based on a
  keyword list or word length.
- **Zoom** -- a restrained punch-in `zoom` operation is generated around
  each emphasis point (not continuous/constant zooming).
- **B-roll** -- keyword-triggered `broll` operations. **These are search
  concept suggestions only** (`query` string) -- Phase 1 does not download,
  search, or select any actual footage.

`planner/generator.py` assembles these into a single time-sorted
`operations` list and wraps it into a full edit-plan dict, including an
empty `modules: []` so the plan still satisfies the pre-existing schema's
required field.

## Validation

`schemas/edit_plan_validate.py` provides:

- `validate_edit_plan_schema(plan)` -- structural validation using this
  repo's existing dependency-free JSON-Schema-subset engine (from
  `schemas/validate.py`), reused rather than duplicated.
- `validate_edit_plan_semantics(plan, media_duration=None)` -- start <
  end, non-negative timestamps, timestamps within `media_duration`,
  required fields per operation type, and overlap rules (`cut`, `caption`,
  and `zoom` operations may not overlap other operations of the same
  type; `broll` and `emphasis` may).
- `validate_edit_plan(plan, media_duration=None)` -- runs both and raises
  a combined `SchemaValidationError` listing every problem found.

The pre-existing `schemas/validate.py` (style-profile validator) is
untouched.

## CLI

```
python -m editiq analyze video.mp4
python -m editiq transcribe video.mp4 --backend mock
python -m editiq transcribe video.mp4 --backend faster-whisper --model base
python -m editiq plan video.mp4 --backend faster-whisper --model base --output edit_plan.json
```

`--backend mock` is the default for `transcribe`/`plan`, so the CLI is
runnable without any ML model installed.

## Pipeline usage (programmatic)

```python
from editiq.pipeline import run_pipeline
from transcription.faster_whisper_backend import FasterWhisperBackend

plan = run_pipeline(
    media_path="video.mp4",
    project={"width": 1080, "height": 1920, "fps": 30},
    backend=FasterWhisperBackend(model_size="base"),
)
```

## Tests

```
pip install pytest
pytest tests/
```

62 tests pass as of this Phase 1 change (17 pre-existing style-profile /
word-level-analyzer tests, unmodified and still passing, plus 45 new Phase
1 tests covering transcription models, the mock backend, normalization,
segmentation, planner rules, edit-plan generation, schema+semantic
validation, the pipeline, and the CLI).

A real end-to-end integration check (not part of the automated suite, run
manually) generated a synthetic video with `ffmpeg` + `espeak-ng` speech
containing "Your money should never sit idle. Put it to work today.",
transcribed it with the real `FasterWhisperBackend` (`tiny` model), ran it
through the full pipeline, and confirmed: real words were detected
("your money should never sit idle" transcribed correctly; "today"
transcribed as "to me", ordinary Whisper variation on synthesized
speech), word-level timestamps were present and increasing, the generated
edit plan validated successfully, and all operation timestamps stayed
within the real 4.092s media duration.

## Current limitations

- **B-roll is a suggestion only.** The `broll` operation's `query` field
  is a search concept string. There is no asset downloader, stock-footage
  API integration, or automatic sourcing in Phase 1.
- **The planner is deterministic and rules-based**, not ML-driven. It does
  not "understand" the video beyond simple keyword/length/pause heuristics.
- **Phase 1 is not a fully autonomous editor.** It produces an edit *plan*
  (JSON), not a rendered video. There is no automatic final-video
  rendering step in this codebase for the operations-based plan (the
  pre-existing `renderer/caption_renderer.py` renders captions for the
  separate style-profile system, not Phase 1 operations).
- **Visual/reference-style matching is not integrated into the Phase 1
  pipeline.** The pre-existing `analyzer/reference_analyzer.py` and
  `analyzer/style_profile_engine.py` are a separate system; Phase 1's
  planner does not currently call into them.
- **Silence-cut detection only looks at gaps between transcript
  segments** (i.e. stretches with no speech at all) -- it does not
  perform sub-word breath/pause detection from raw audio.
- **`analyze_media()` is currently minimal**: it only probes duration via
  `ffprobe`. It is a stable extension point for richer analysis later.
- **Captions/rendering are not claimed as automatic** beyond producing
  `caption` operations with text and timing; there is no caption-burning
  or video-rendering step for Phase 1 output.

## Roadmap (suggested Phase 2)

1. Wire the b-roll `query` suggestions to an actual stock-footage search
   (still requiring explicit user/human selection before download).
2. Add a rendering step that consumes a validated Phase 1 edit plan and
   produces an actual output video (captions burned in via
   `renderer/caption_renderer.py` or a new renderer, cuts applied via
   ffmpeg).
3. Sub-word silence/pause detection from raw audio (not just inter-segment
   gaps) for finer-grained cut suggestions.
4. Bridge the style-profile system (`analyzer/`) into the Phase 1 planner
   so captions can inherit a reference video's visual style.
5. Broaden Faster-Whisper integration testing (currently one manual,
   real-audio smoke test; consider adding it as an opt-in `pytest` marker
   for CI environments that have the model available).
