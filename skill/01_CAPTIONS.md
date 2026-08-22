# EditIQ Caption Engine V1

## PURPOSE

Create deterministic, reference-matched dynamic captions.

The caption engine must reproduce the selected STYLE_PROFILE instead of inventing a new visual style.

---

## INPUTS

The caption engine receives:

1. Target video
2. Transcript
3. STYLE_PROFILE
4. EDIT_PLAN
5. Optional word-level timestamps
6. Optional face/subject position data

---

## CAPTION PIPELINE

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

## TYPOGRAPHY

Use STYLE_PROFILE values exactly when available.

Parameters:

- font family
- font weight
- font size
- fill color
- highlight color
- opacity
- letter spacing
- line height
- alignment

Do not substitute a different font unless the required font is unavailable.

If substitution is required, select the closest available font by visual width and weight.

---

## COLOR

Use the STYLE_PROFILE.

Do not invent new colors.

Primary text:

caption.fill

Highlighted text:

caption.highlight

If no highlight color exists, use the primary fill.

---

## EFFECTS

Apply only effects specified by STYLE_PROFILE.

Possible effects:

- stroke
- shadow
- glow
- blur
- background
- opacity

Never add a glow merely because captions should look "premium".

---

## POSITION

Use STYLE_PROFILE position unless EDIT_PLAN explicitly overrides it.

Supported modes:

- fixed
- safe_area
- below_chin
- reference

---

## BELOW-CHIN MODE

When the user requests:

"Text chin ke neeche"

the engine must:

1. detect the face
2. estimate chin position
3. calculate caption bounding box
4. place the caption below the chin
5. maintain safe margins
6. prevent unnecessary overlap with the speaker

---

## SAFE AREA

For vertical 9:16 video:

```text
width = 1080
height = 1920
