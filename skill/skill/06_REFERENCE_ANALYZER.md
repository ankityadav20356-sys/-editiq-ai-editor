# EditIQ Reference Video Analyzer V2

## PURPOSE

Analyze a reference video and convert its visual editing style into structured, measurable data.

The reference video is the source of truth.

Do not create a "similar" style when the user asks for an exact match.

---

# ANALYSIS PRIORITY

Analyze caption style in this order:

1. Caption location
2. Font family
3. Font weight
4. Font size
5. Text width
6. Text color
7. Highlight color
8. Stroke
9. Shadow
10. Glow
11. Opacity
12. Line spacing
13. Alignment
14. Word grouping
15. Word highlighting
16. Animation
17. Timing behavior

---

# FRAME SAMPLING

Use intelligent sampling.

Do not process every frame unless QUALITY mode is requested.

FAST mode:

- sample representative frames
- detect stable caption regions
- estimate style parameters

QUALITY mode:

- inspect more frames
- compare repeated caption appearances
- identify animation states
- calculate more accurate visual measurements

---

# VIDEO PROPERTIES

Extract:

width
height
fps
duration
frame_count
aspect_ratio

---

# CAPTION REGION

Identify the region where captions appear.

Record:

{
  "x": 0,
  "y": 0,
  "width": 0,
  "height": 0
}

Normalize coordinates:

x = x / video_width
y = y / video_height
width = width / video_width
height = height / video_height

This allows the style to work across different resolutions.

---

# TYPOGRAPHY ANALYSIS

Estimate:

font_family
font_weight
font_size_px
letter_spacing
line_height
alignment

If exact font identification is impossible:

1. estimate visual characteristics
2. compare available fonts
3. select the closest measurable match
4. record confidence

Never claim an exact font when the evidence is insufficient.

---

# COLOR ANALYSIS

Extract dominant caption colors.

Record colors as:

#RRGGBB

Analyze:

- primary text
- highlighted text
- stroke
- shadow
- background
- glow

Use multiple samples rather than relying on a single pixel.

---

# SHADOW ANALYSIS

Estimate:

shadow_enabled
shadow_color
shadow_opacity
shadow_offset_x
shadow_offset_y
shadow_blur

If there is no visible shadow:

shadow_enabled = false

Do not add one.

---

# GLOW ANALYSIS

Determine whether a glow exists.

Record:

glow_enabled
glow_color
glow_opacity
glow_radius

Only enable glow when it is visually supported by the reference.

---

# STROKE ANALYSIS

Determine:

stroke_enabled
stroke_color
stroke_width
stroke_opacity

If no stroke is visible:

stroke_enabled = false

---

# POSITION ANALYSIS

Determine whether captions are:

- centered
- left aligned
- right aligned
- above speaker
- below speaker
- below chin
- fixed position
- subject-relative

Record normalized coordinates.

---

# SUBJECT RELATIVE POSITION

If captions move relative to the speaker:

1. detect face
2. estimate face bounding box
3. estimate chin location
4. calculate caption offset
5. store normalized relationship

Example:

{
  "mode": "below_chin",
  "offset_y": 0.04
}

---

# WORD GROUPING

Analyze how many words appear per caption event.

Determine:

words_per_group
characters_per_group
line_count

Look for consistent patterns.

---

# WORD HIGHLIGHTING

Determine whether individual words change:

- color
- weight
- size
- opacity
- scale

Record:

highlight_enabled
highlight_color
highlight_behavior

---

# ANIMATION ANALYSIS

Compare consecutive frames around caption appearance.

Look for:

- fade
- scale
- pop
- slide
- reveal
- typewriter
- word-by-word appearance
- no animation

Record:

animation_type
animation_duration_ms
animation_strength

Do not invent animation when no animation is visible.

---

# STYLE PROFILE

The final analysis should produce a structured STYLE_PROFILE.

Example:

{
  "version": 2,
  "video": {},
  "caption": {
    "font_family": "",
    "font_weight": 700,
    "size_px": 0,
    "fill": "#FFFFFF",
    "highlight": "#FFFFFF",
    "position": {},
    "shadow": {},
    "stroke": {},
    "glow": {},
    "animation": {}
  },
  "confidence": {}
}

---

# CONFIDENCE

Every uncertain property should have a confidence value between:

0.0

and

1.0

Example:

{
  "font_family": 0.72,
  "font_weight": 0.94,
  "fill": 0.98
}

High confidence:

>= 0.85

Medium confidence:

0.60–0.84

Low confidence:

< 0.60

---

# REFERENCE MATCH RULE

When the user says:

"Make Video 2 exactly like Video 1"

the analyzer must prioritize measurable reference properties.

Do not:

- choose a random modern font
- add random glow
- change colors
- move captions arbitrarily
- add unnecessary animations
- redesign the caption style

---

# FAILURE HANDLING

If a property cannot be detected:

1. analyze additional frames
2. compare multiple caption instances
3. use the most consistent measurement
4. record confidence
5. leave unsupported effects disabled

Never fabricate measurements.

---

# OUTPUT

The analyzer produces:

style_profile.json

This file becomes the single source of truth for the caption renderer.

Pipeline:

REFERENCE VIDEO
↓
REFERENCE ANALYZER
↓
STYLE_PROFILE
↓
CAPTION RENDERER
↓
TARGET VIDEO
