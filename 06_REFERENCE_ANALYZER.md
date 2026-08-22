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

```text
width
height
fps
duration
frame_count
aspect_ratio
