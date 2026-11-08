# Stage 1 — Source-Generation Prompt

Read this file only while constructing an image-generation or explicitly requested image-editing call. Do not read post-generation references during this stage.

## Generation backend

Default to built-in imagegen. When the user requests GPT Image 2.6 or the external image API route, load [the GPT Image 2.6 profile](image-models/gpt-image-2.6.md) and its adjacent JSON configuration during this stage. Only Sunburst and Flare are adapted for now; do not substitute other models. If the user says only “external API”, use the profile's Sunburst default.

The model profile controls transport parameters only; never copy it into the visual prompt. Honor user parameter choices. Keep default prompt augmentation enabled (do not pass `--no-augment` unless explicitly requested), and save the raw and effective prompt. Both backends return `01_source.png` to the same refinement workflow. Keep credentials out of all prompts and records. Resolve transport errors separately from image-quality retries.

## Allowed inputs

When the user supplies no stronger style reference, load:

- `../assets/reference-kafka-style.png` as Image 1
- `../assets/reference-xiaowanzhou-style.png` as Image 2
- `../assets/reference-yoimiya-style.png` as Image 3
- Do not load `../assets/reference-action-interaction.png` by default or automatically treat Image 4 as an action reference.

Treat user-provided images as references unless the user explicitly asks to edit the supplied image.

## Mandatory official-character research gate

Before every generation or creative edit of a named or recognizable character:

1. Search first-party sources for canonical identity, appearance, clothing, palette, props, and signature motifs. Prefer collecting and using multiple clear, reliable official reference images of the same character and costume/version, together covering the face, hairstyle, and key clothing details. Cross-check distinctive identity features across the references to avoid a generic likeness. Do not mix different characters, skins, costumes, or mechanical/human forms, or force a fixed image count.
   Check coverage rather than a fixed image count: the references should clearly show the face/eyes, hairstyle and head accessories, and upper-body costume. Two complementary clear official images can be sufficient; duplicate crops or reposts of the same artwork do not count as independent coverage. If a feature is obscured or references disagree, seek another official close-up, view, or clear frame from the same costume/form before generating. Prefer a small complementary set (often 3–4 images when needed), not many redundant images. Do not mix forms to increase the count. Record any remaining gaps instead of inventing details.
2. Save `00_official_character_research.md` with the canonical name/version, the actual official source URLs and reference images used, verified visual facts, and clearly separated inferences. Record gaps in reference coverage; if only one official image is available, state that explicitly rather than claiming multiple references.
3. Use the brief as the identity authority without copying logos, readable marks, slogans, or long source text.
4. Record original/non-character subjects as `official_character_research_status=not_applicable`.
5. Stop and ask for an approved reference when identity is ambiguous or no reliable official source exists.

## New-generation payload

For the first attempt, render the template below. For retries, follow the retry rule at the end of this file.

- Replace `<character>` with the requested character name and costume/version.
- Replace `<pose-plan>` and `<expression-plan>` with concrete visual directions selected before each generation. Save them with the rendered prompt and attempt number. These are creative choices, not diagnostics.
- Replace `<verified-character-appearance-summary>` with a concise, self-contained summary of verified visual facts from the saved research. For original subjects, use the user's appearance description and identify it as an original design.
- Inline the actual appearance facts; a local file path or instruction to read a Markdown file is not a substitute. The image model cannot read local research files.
- Keep workflow instructions, source-validation thresholds, diagnostics, conversion details, and previous results out of these placeholders. Preserve the artistic grid target already written in the template; do not derive or adjust it from later-stage checks.

```text
Use case: stylized-concept
Asset type: coarse pixel-art portrait
Primary request: Create one recognizable <character> as coarse pixel art.

Priority 1 — pixel language: Internally design on a 24 × 24 logical canvas and enlarge with nearest-neighbor only. Use Images 1–3 as examples of uniform pixel cells, readable detail density, stair-stepped contours, and simplified character features. Follow the 24 × 24 logical canvas target specified above rather than copying a reference image’s exact dimensions. Keep all boundaries on one grid. Use flat colors without a fixed palette-size limit.

Pixel-block constraint: Do not use extra shading, gradients, or clusters of near-identical colors to simulate detail. When a detail cannot be expressed with a few clear logical cells, symbolize and simplify it into fewer cells. Keep detailed regions at the same cell scale as the rest of the image; never magnify them locally or use continuous tonal steps.

Priority 2 — character and pose: Draw one natural upper-body portrait ending at the upper chest. Default to a natural three-quarter upper-body view, with the head, chest, and shoulders facing broadly the same direction. Show the angle through the shoulder line and torso perspective, not an isolated head turn. Allow a small natural head adjustment, but avoid a pronounced neck twist, looking back over the shoulder, or a forced head tilt. Follow an explicitly requested pose when provided. Avoid a flat, straight-on ID-photo composition. Keep the head and hair dominant, center the subject horizontally, and shift it upward by about 1–2 logical rows.
Pose for this image: <pose-plan>
Expression for this image: <expression-plan>
Create a fresh portrait composition following these directions while preserving the character identity and pixel-art constraints.

Priority 3 — eyes and anatomy: Draw natural, readable eyes with a coherent gaze. Let eye height, width, placement, and visible iris/pupil shapes follow the overall viewing angle and natural occlusion by hair, glasses, or props. Keep the eye structures clear and visually consistent with the face; avoid obvious misalignment, broken shapes, or unexplained distortions. Keep the head-to-shoulder relationship compact and natural. Show only the small amount of neck needed between the jaw and the collar or shoulders; do not connect the head and body with an elongated vertical column of skin. Let the neck merge naturally into the shoulder line. Preserve the character’s costume and accessories without lengthening the neck to display a necklace, collar, or ornament.

Priority 4 — silhouette: Use a one-logical-pixel pure-black outline around the complete subject. Make the lowest occupied subject row a continuous black baseline, with at least one clean background row below it. Use a completely uniform pure-white background. The generated PNG must be fully opaque: every background pixel and every subject pixel has alpha 255. Do not generate transparency, partial transparency, a checkerboard, shadows, gradients, or background texture.

Verified character appearance: <verified-character-appearance-summary>
Use this inline summary and the official character images for identity, hairstyle, costume, palette, and signature motifs. Do not copy logos, readable marks, slogans, or text from official sources.

Reference rule: Images 1–3 guide only pixel structure, detail density, outline weight, and simplification. Image 1 demonstrates clear hair masses and readable contours; Image 2 demonstrates flat color blocks and simplified small details; Image 3 demonstrates how to organize complex hair ornaments, rope knots, and costume details on a uniform pixel grid while keeping a natural, readable expression. Learn its detail selection and expression clarity without copying its specific mouth shape. Do not copy their identity, palette, pose, clothing, or accessories. In particular, do not copy Image 2’s hair covering one eye; eye visibility follows the requested character and pose. Follow the user's requested character and action.

Character-reference rule: Use official character images only for identity, hairstyle, clothing, palette, and other appearance features. Do not use them as references for action, pose, or composition.

Avoid: transparent or partially transparent pixels, checkerboard backgrounds, fine hair strands, micro-texture, tiny highlights, sub-cell marks, mixed cell sizes, dithering, gradients, antialiasing, soft edges, glossy illustration rendering, text, watermark, extra characters, a frontal mugshot, a long thin neck, visibly incoherent gaze, broken eye shapes, or a broken exterior/bottom outline.
```

## Explicit user-source edit payload

Use this block only when the user explicitly asks to edit their supplied source. Never use it to repair a generated result.

```text
Edit the supplied source with the minimum possible change. Preserve its composition, crop, pixel scale, palette, silhouette, head turn, face and jaw shape, hair mass, neck width, shoulder line, hand/prop placement, expression, and exterior outline. Correct only <user-requested defect>. Do not redesign or redraw unrelated areas.
```

## Retry rule

On retry, write a fresh image-generation prompt following this skill’s Stage 1 generation guidelines and the original user request. Do not merely patch the previous prompt or change its placeholders. Natural expressions may repeat; do not exaggerate them to force variation.

Reuse the original official character references and style references, but never use images generated in previous attempts as input. Do not include downstream validation results or processing details. Save the exact prompt used for each attempt.
