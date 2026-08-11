# Coarse Pixel-Art Generation Prompt

Use the following structure when generating a character source image. Treat user-provided images as style and density references, not edit targets. When the user supplies no stronger reference, first load:

- `../assets/reference-24x24-block-style.png` as Image 1
- `../assets/reference-coarse-density-a.png` as Image 2
- `../assets/reference-coarse-density-b.png` as Image 3
- When the request includes a clear action or handheld-object interaction, also load `../assets/reference-action-interaction.png` as Image 4

Before writing or sending this prompt, complete the skill's mandatory official-character research gate. For a named or recognizable character, use the saved official-character research brief as the identity authority and keep verified facts separate from inference. For an original/non-character subject, record `official_character_research_status=not_applicable` instead of inventing official data. Never call image generation before this gate is complete.

```text
Use case: stylized-concept
Asset type: source image for a layered RYBW 3MF plaque
Primary request: Create one recognizable <character> as coarse pixel art for a printable plaque.

Priority 1 — pixel language: Internally design on exactly a 24 × 24 logical canvas and enlarge with nearest-neighbor only. Treat 24 × 24 as a deliberate preventive undershoot because generated images often contain more logical cells than requested. Match Images 1–3 for large uniform cell size, low information density, stair-stepped contours, and symbolic detail. Keep all boundaries on one grid. Use about 8–12 flat colors.

Priority 2 — character and pose: Draw one natural upper-body portrait ending at the upper chest. Default to a lively three-quarter head turn with both eyes visible. Preserve perspective through asymmetric cheek, jaw, nose, hair, and shoulder shapes; do not flatten the face into a frontal portrait. Keep the head and hair dominant, center the subject horizontally, and shift it upward by about 1–2 logical rows.

Priority 3 — eyes and anatomy: Build both eyes from the same vertical pixel template. Give them identical top/bottom anchor rows and identical iris/pupil row counts, with aligned centers and matching gaze. Three-quarter perspective may make the far eye at most one logical cell narrower, but never shorter. Hair, glasses, or props may overlap the eye white; do not let occlusion shorten an iris/pupil or move an eyelid anchor. Keep the neck short and naturally broad at the base, flowing into the collar and shoulders; unless the character design requires otherwise, the visible neck opening is roughly one-quarter to one-third of the lower-face width and the collar begins within a few rows below the jaw.

Priority 4 — printable silhouette: Use a one-logical-pixel pure-black outline around the complete subject. Make the lowest occupied subject row a continuous black baseline, with at least one clean background row below it. Use a uniform pure-white or easily removable flat background.

Official-character research rule: Use the verified research brief at `<official-character-research-file>` for canonical identity, appearance, costume, palette, props, and signature motifs. Treat any unverified adaptation as inference. Do not copy logos, readable marks, slogans, or text from official sources.

Reference rule: Images 1–3 control only cell scale, information density, outline weight, and simplification. Do not copy their identity, palette, pose, clothing, hand placement, drink, or accessories. Follow the user's requested character and action.

Action-reference rule: If Image 4 is present, use it only as an example of readable action staging, hand/prop integration, head-dominant framing, and preserving a lively three-quarter face when an object approaches the face. Do not copy its identity, hairstyle, palette, clothing, hand side, exact pose, drink, or accessories. Replace all content with the user's requested character, action, and object.

Avoid: fine hair strands, micro-texture, tiny highlights, sub-cell marks, mixed cell sizes, dithering, gradients, antialiasing, soft edges, glossy illustration rendering, text, watermark, extra characters, a frontal mugshot, a long thin neck, unequal eye height, unequal iris/pupil row counts, or a broken exterior/bottom outline.
```

## Local-correction addendum

When the input image already has the desired look and the user names one defect, append this instead of restating all generation rules:

```text
Edit the supplied image with minimum possible change. Preserve the exact composition, crop, pixel scale, palette, silhouette, three-quarter head turn, face and jaw shape, hair mass, neck width, shoulder line, hand/prop placement, expression, and exterior outline. Correct only <named defect>. Do not redesign or redraw unrelated areas.
```

If the result still looks like a polished illustration, uses many tiny cells, places the subject too low, minimizes the head, becomes frontal, hides an eye, misaligns the eyes or pupils, creates a long thin neck, touches the bottom edge, or lacks the closed pure-black baseline, regenerate. Do not correct logical density or major geometry later in the conversion pipeline.

Before accepting the source, run Perfect Pixel auto-detection as a diagnostic. The requested `24 × 24` is prompt guidance; do not require the detector to return 24. Require approximately `55–72` detected cells per axis. If either axis is below `55` or exceeds `72`, regenerate with an adjusted logical density while preserving the coarse style. Do not resize or force a downstream grid.
