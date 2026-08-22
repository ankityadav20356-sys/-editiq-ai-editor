# EditIQ Reference Analyzer V1

## PURPOSE

Convert a reference video into a precise, reusable STYLE_PROFILE.

The reference is the source of truth for the requested visual style.

Do not imitate the reference vaguely.

Measure and describe its actual properties.

---

# ANALYSIS MODES

## FAST

Default mode.

Use intelligent frame sampling.

Analyze only frames that contain relevant visual information.

Use FAST when:

- a style profile already exists
- the user wants a normal edit
- the reference is already known
- maximum precision is not requested

---

## QUALITY

Use when:

- user says "exactly like reference"
- user says "same caption style"
- creating a new style profile
- FAST result does not match
- user requests maximum accuracy

QUALITY mode performs deeper analysis.

---

# FRAME SAMPLING

Do NOT inspect every frame by default.

First determine:

- video duration
- FPS
- resolution
- scene changes
- caption appearance intervals

Prioritize frames where:

1. captions first appear
2. captions change
3. highlighted words appear
4. caption animation starts
5. caption animation ends
6. caption position changes
7. text color changes
8. motion graphics appear
9. scene/lighting changes

If the caption style is ambiguous, increase sampling around the relevant timestamps.

---

# CAPTION ANALYSIS

Extract:

### Typography

- font family candidate
- font weight
- font size
- uppercase/lowercase behavior
- letter spacing
- line height
- text width
- text height

### Color

- primary fill color
- highlighted word color
- secondary color
- opacity
- gradient if present

### Effects

- stroke
- shadow
- glow
- blur
- outline
- background box
- background opacity

### Layout

- horizontal position
- vertical position
- alignment
- maximum line width
- words per line
- line count
- distance from subject
- distance from safe-area edges

### Animation

Determine:

- animation type
- entrance duration
- exit duration
- word timing
- character timing
- scale change
- opacity change
- position change
- easing

Do not describe animation only with words such as "smooth" or "dynamic".

Convert it into measurable parameters.

---

# POSITION ANALYSIS

The renderer works in normalized coordinates where possible.

Use:

```text
x = 0.0 → left
x = 0.5 → center
x = 1.0 → right

y = 0.0 → top
y = 0.5 → center
y = 1.0 → bottom
