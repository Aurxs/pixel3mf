# Stage 1 — Source-Generation Prompt

Read this file only while constructing an image-generation or explicitly requested image-editing call. Do not read post-generation references during this stage.

## Generation backend

Default to built-in imagegen. When the user requests GPT Image 2.6 or the external image API route, load [the GPT Image 2.6 profile](image-models/gpt-image-2.6.md) and its adjacent JSON configuration during this stage. Only Sunburst and Flare are adapted for now; do not substitute other models. If the user says only “external API”, use the profile's Sunburst default.

The model profile controls transport parameters only; never copy it into the visual prompt. Honor user parameter choices. Keep default prompt augmentation enabled (do not pass `--no-augment` unless explicitly requested), and save the raw and effective prompt. Both backends return `01_source.png` to the same refinement workflow. Keep credentials out of all prompts and records. Resolve transport errors separately from image-quality retries.

## Allowed inputs

When the user supplies no stronger style reference, load:

- `../assets/reference-yoimiya-style.png` (宵宫) as Image 1
- `../assets/reference-xiaowanzhou-style.png` (小挽昼) as Image 2
- `../assets/reference-kafka-style.png` (卡芙卡) as Image 3
- `../assets/reference-valeri-style.png` (瓦列里) as Image 4
- Use these four bundled style references. Attach official character references after them, starting with Image 5.

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
- Replace `<expression-plan>` with concrete visual directions selected before each generation. Save the expression plan and any explicit pose directions with the rendered prompt and attempt number. These are creative choices, not diagnostics.
- Pose directions are optional. Insert `Pose for this image: <pose-plan>` immediately before the expression line only when the user specifies a pose or the requested action needs one; otherwise omit the entire line and use the template's general composition guidance. User instructions take precedence. Do not default to a facing direction, turn angle, head tilt, shoulder height, or gaze toward the viewer. Do not routinely add head tilt or a backward glance merely to convey a natural, lively, or playful expression. Choose any explicit pose independently of the style references.
- When multiple works or pose plans are already available in the current conversation, avoid repeatedly using the same combination of head tilt, body orientation, and gaze. Let variation serve the character's expression; do not use a fixed left/right rotation or exaggerate poses just to make them different.
- Replace `<verified-character-appearance-summary>` with a concise, self-contained summary of verified visual facts from the saved research. For original subjects, use the user's appearance description and identify it as an original design.
- Inline the actual appearance facts; a local file path or instruction to read a Markdown file is not a substitute. The image model cannot read local research files.
- Keep workflow instructions, source-validation thresholds, diagnostics, conversion details, and previous results out of these placeholders. Preserve the artistic grid target already written in the template; do not derive or adjust it from later-stage checks.

```text
Use case: stylized-concept
Asset type: coarse pixel-art portrait
Primary request: Create one recognizable <character> as coarse pixel art.

Priority 1 — pixel language: Internally design on a 24 × 24 logical canvas and enlarge with nearest-neighbor only. Use Images 1–4 as examples of uniform pixel cells, readable detail density, stair-stepped contours, and simplified character features. Follow the 24 × 24 logical canvas target specified above rather than copying a reference image’s exact dimensions. Keep all boundaries on one grid. Use flat colors without a fixed palette-size limit.

Pixel-block constraint: Do not use extra shading, gradients, or clusters of near-identical colors to simulate detail. Express details as coherent pixel clusters, simplifying redundant texture while preserving facial expression and distinctive character features. Keep detailed regions at the same cell scale as the rest of the image; never magnify them locally or use continuous tonal steps.

Priority 2 — character and composition: Draw one natural upper-body portrait ending at the upper chest. Use a non-frontal overall composition, leaving the facing direction and degree of turn unspecified. Let the shoulder line and torso perspective establish the orientation; do not rely solely on turning or tilting the head to avoid a frontal composition. Keep the head, neck, and shoulders naturally coordinated. Head tilt and looking back toward the viewer are optional expressive choices, not default features of the portrait. Follow an explicitly requested pose when provided. Keep the head and hair dominant, center the subject horizontally, and shift it upward by about 1–2 logical rows.
Expression for this image: <expression-plan>
Create a fresh portrait composition following these directions while preserving the character identity and pixel-art constraints.

Priority 3 — eyes, mouth, and anatomy: Draw natural, readable eyes with a coherent gaze. Let eye height, width, placement, and visible iris/pupil shapes follow the overall viewing angle and natural occlusion by hair, glasses, or props. Keep the eye structures clear and visually consistent with the face; avoid obvious misalignment, broken shapes, or unexplained distortions. Keep the neck short and proportionate. Do not draw a long or elongated neck. Keep the shoulders relaxed and naturally proportioned to the torso. Preserve the character’s costume and accessories.

Where the eyes are visible, build their contours, lashes, sclera, irises, pupils and highlights, where present, from whole square cells on the SAME coarse pixel grid as the face, with one flat color per cell. Use coherent pixel clusters and whole-cell stair steps, without diagonal half-cells, sub-cell strokes, antialiasing, smooth vector-like curves, finely drawn eyelashes, iris gradients or sub-cell highlights. Preserve readable eye shapes and gaze at the existing cell scale; simplify small details rather than drawing the eyes at a finer resolution. Do not force every eye component to appear separately, prescribe fixed pixel counts, or make the two eyes identical; preserve natural perspective, expression and occlusion.

Where the mouth is visible, build it from a few whole square cells on the SAME coarse pixel grid as the face, with one flat color per cell. Match the expression using whole-cell stair steps, without curves, diagonal half-cells, sub-cell strokes, antialiasing or finely drawn lips. Both open and closed mouths are valid; a short pixel line or single cell is allowed when it fits the expression and scale. For an open mouth, use a simple flat color cluster; a dark mouth interior is allowed. Let the mouth color meet the skin directly, without an extra dark outline or enclosing dark ring around it. Never draw teeth, tooth rows, individual teeth or fangs. Do not use white or pale tooth-like bars inside the mouth.

Priority 4 — silhouette: Use a one-logical-pixel pure-black exterior outline around the complete subject; do not apply this outline to the mouth. Make the lowest occupied subject row a continuous black baseline, with at least one clean background row below it. Use a completely uniform pure-white background. The generated PNG must be fully opaque: every background pixel and every subject pixel has alpha 255. Do not generate transparency, partial transparency, a checkerboard, shadows, gradients, or background texture.

Verified character appearance: <verified-character-appearance-summary>
Use this inline summary and the official character images for identity, hairstyle, costume, palette, and signature motifs. Do not copy logos, readable marks, slogans, or text from official sources.

Reference rule: Images 1–4 guide only pixel structure, detail density, outline weight, and simplification. Image 1 demonstrates readable expression, an open pixel mouth, and simplified complex hair ornaments, rope knots, and costume details. Image 2 demonstrates coarse flat color blocks, compact short-hair masses, and readable features partly occluded by hair. Image 3 demonstrates clear layered hair masses and simplified clothing details. Image 4 demonstrates short-hair clusters and the simplification of complex collars and shoulder armor. Learn their pixel construction and detail selection, without assigning any image as a pose template. Do not copy their identity, palette, pose, clothing, or accessories. Eye visibility follows the requested character and pose, not a reference image's hair occlusion. Both open and closed mouths remain valid. Follow the user's requested character and action.

Character-reference rule: Use official character images only for identity, hairstyle, clothing, palette, and other appearance features. Do not use them as references for action, pose, or composition.

Avoid: transparent or partially transparent pixels, checkerboard backgrounds, fine hair strands, micro-texture, tiny highlights, sub-cell marks, mixed cell sizes, dithering, gradients, antialiasing, soft edges, glossy illustration rendering, text, watermark, extra characters, a long or elongated neck, visibly incoherent gaze, broken eye shapes, or a broken exterior/bottom outline.
```

## Explicit user-source edit payload

Use this block only when the user explicitly asks to edit their supplied source. Never use it to repair a generated result.

```text
Edit the supplied source with the minimum possible change. Preserve its composition, crop, pixel scale, palette, silhouette, head turn, face and jaw shape, hair mass, neck width, shoulder line, hand/prop placement, expression, and exterior outline. Correct only <user-requested defect>. Do not redesign or redraw unrelated areas.
```

## Retry rule

On retry, write a fresh image-generation prompt following this skill’s Stage 1 generation guidelines and the original user request. Do not merely patch the previous prompt or change its placeholders. Natural expressions may repeat; do not exaggerate them to force variation.

A quality retry need not change an otherwise suitable pose. If the user identifies repetitive posing, reconsider the overall composition rather than merely mirroring it, slightly changing the tilt, or rewording the same pose. An occasional natural head tilt alone is not a reason to regenerate.

On quality retries, preserve the initial logical-grid target and intended detail density unless the user requests a change. For scattered results, improve pixel grouping, spacing, and contour continuity rather than requesting lower resolution, coarser pixels, or reduced character detail.

Reuse the original official character references and style references, but never use images generated in previous attempts as input. Do not include downstream validation results or processing details. Save the exact prompt used for each attempt.
