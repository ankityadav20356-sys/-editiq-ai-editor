# EditIQ Caption Engine V1

## PURPOSE

Create deterministic, reference-matched dynamic captions.

The caption engine must reproduce the selected STYLE_PROFILE instead of inventing a new visual style.

---

# INPUTS

The caption engine receives:

1. Target video
2. Transcript
3. STYLE_PROFILE
4. EDIT_PLAN
5. Optional word-level timestamps
6. Optional face/subject position data

---

# CAPTION PIPELINE

Target Video
↓
Transcript
↓
Word-level timing
↓
Caption grouping
↓
STYLE_PROFILE
↓
Position calculation
↓
Typography
↓
Effects
↓
Animation
↓
Render
↓
Validation

---

# TRANSCRIPTION

If word-level timestamps are available, use them.

If they are unavailable:

1. generate word-level timestamps using the available transcription engine
2. preserve original speech timing
3. do not manually guess timings unless no transcription system is available

Caption timing must follow speech.

---

# CAPTION GROUPING

Do not create arbitrary long sentences.

Use the STYLE_PROFILE to determine:

- maximum words per line
- maximum lines
- visual width
- pause boundaries
- sentence boundaries
- emphasis boundaries

Prefer visually readable caption groups.

Example:

BAD:

```text
You know Bali is number one destination for tourists for people who love the beach
