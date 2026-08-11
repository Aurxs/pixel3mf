---
name: pixel-art-to-3mf
description: Use this skill when the user wants to turn an anime/game character name or a provided reference image into a printable layered 3MF inside a project that contains a cloned Lumina-Layers repository. Before any image generation or editing of a recognizable character, mascot, or branded figure, research official character sources and use that brief as the visual identity authority. The skill covers image generation, background removal to transparency, square-canvas preparation, Perfect Pixel refinement, optional cleanup, and Lumina conversion. Default behavior is a 65 mm × 65 mm square workflow with full intermediate outputs saved in a timestamped output run folder, using the BambuLab PLA 4-color RYBW LUT, 1.2 mm backing, double-sided structure, no hanging loop, pixel modeling mode, quantize_colors 256, hue protection 0.6, and batch conversion when possible.
---

# Pixel Art to 3MF

Use this skill for end-to-end **character/reference image → pixel-art-friendly source image → refined low-resolution pixel art → Lumina 3MF** workflows.

## When to use this skill
Use this skill when the user wants any of the following:
- Generate an anime / game / cartoon character image and turn it into a printable 3MF.
- Provide a reference image and convert it into a low-resolution pixel-art-style 3MF.
- Run a repeatable pipeline in a project that already contains `Lumina-Layers/`.
- Keep all intermediate files for inspection and later parameter tuning.

## Required inputs
At least one of:
- a character name / subject description, or
- a source image / reference image.

If a source image is not provided, create one first with image generation. Prefer a single centered subject with clean silhouette and simple colors.

## Mandatory official-character research gate

Before every image-generation or image-editing call in this skill—including the first source, a retry, a repair, or a variant—complete this gate. Direct conversion and deterministic local processing do not count as image generation and do not need a new search.

- For a named or recognizable anime, game, cartoon, film, historical, mascot, or branded character, use web search first. Use only the official character page, publisher/developer/franchise site, official guide, press kit, or another first-party source. Do not substitute a secondary source unless the user explicitly allows it.
- Search narrowly for the canonical identity, for example: `<character name> official character profile` and `<character name> official site`. Do not generate while the search is pending.
- Save `00_official_character_research.md` in the run folder before generation. Record the canonical name/version, 1–4 official source URLs (prefer 2–4 when available), verified visual attributes (face/hair/body, clothing, palette, props, motifs), and an explicit `Verified facts` versus `Inferences` distinction. Treat the brief as the identity source of truth for the prompt, but do not copy logos, readable marks, slogans, or long source text.
- If the request is an original/non-character subject, still evaluate the gate and record `official_character_research_status=not_applicable`; never invent an official profile. If a named character has no reliable official source or the identity is ambiguous, stop before generation and ask for an approved reference or permission to proceed without official data.
- Carry the research file path and source URLs into `manifest.json` as `official_character_research_path` and `official_character_sources`.

## Bundled generation references
When the user does not provide a stronger style reference, use these bundled assets:
- `assets/reference-24x24-block-style.png` — reference for block size, one-pixel outline, stair-stepped silhouette, palette simplicity, and low information density.
- `assets/reference-coarse-density-a.png` and `assets/reference-coarse-density-b.png` — empirical references for the preferred coarse character-pixel density; their Perfect Pixel detections are approximately `51 × 50` and `47 × 47`.
- `assets/reference-action-interaction.png` — optional action-composition example for requests where the subject performs a clear action or interacts with a handheld prop.

Load the first three assets with the image-viewing tool before generation so they are available to the image generator. When the request includes a clear action or object interaction, additionally load `reference-action-interaction.png`. Use it only for action readability, hand/prop integration, head-dominant upper-body framing, and keeping a lively three-quarter pose while an object approaches the face. Never copy its character identity, hairstyle, palette, clothing, hand side, exact pose, drink, or accessories. Determine character details, action, and object from the user's request.

## Fixed defaults for this project
Unless the user overrides them, use these exact defaults:
- **Canvas rule**: force a square composition.
- **Default framing**: a natural upper-body portrait—head, shoulders, and upper chest. Keep the subject horizontally centered but shift it upward by about `1–2` logical pixels so the head and hair are the dominant visual mass. Do not extend below the chest unless the user explicitly requests a wider framing.
- **Final physical size**: `65 mm × 65 mm`.
- **Generation density**: explicitly request an internal `24 × 24` logical canvas, rendered only as a nearest-neighbor enlargement. This is a deliberate preventive undershoot because image generators often produce a finer grid than requested. Keep every contour and color boundary on one uniform grid.
- **Density acceptance**: treat the requested `24 × 24` as prompt guidance, not the measured output requirement. Use Perfect Pixel auto-detection after generation and prefer approximately `44–60` detected cells per axis for a square character portrait. Reject and regenerate when either axis exceeds `60`; values below `44` may be accepted when the subject remains readable and visually matches the bundled coarse references. Never resize to force this range.
- **Silhouette outline**: fully enclose the subject in a one-logical-pixel pure-black exterior outline. Make the bottom-most occupied subject row a continuous black baseline and leave at least one background row below it.
- **Default pose**: use a readable three-quarter head turn by default, with both eyes visible and the shoulders allowed to angle naturally. Use a fully frontal or full-profile pose only when the user explicitly requests it.
- **Facial alignment**: preserve the lively three-quarter geometry while building both eyes from the same vertical pixel template. Use the same top and bottom rows and the same iris/pupil row counts, with aligned centers and matching gaze. Perspective may make the far eye at most one logical cell narrower, but never shorter. Hair, glasses, or props may overlap the sclera only; occlusion must not shorten the iris/pupil or move the eyelid anchors.
- **Head–neck silhouette**: keep the neck short and naturally broad at its base, flowing into the collar and shoulders. Unless the character reference clearly says otherwise, avoid a long narrow neck stalk; keep the visible neck opening roughly one-quarter to one-third of the lower-face width and begin the collar/shoulders within a few logical rows below the jaw.
- **Refinement grid**: do not force a downstream grid; preserve Perfect Pixel's automatic detection result.
- **Backing thickness**: `1.2 mm`.
- **Structure mode**: `Double-sided`.
- **Hanging loop**: disabled.
- **LUT**: `Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy` from Lumina’s `lut-npy预设/bambulab/` preset set.
- **Modeling mode**: `pixel` / pixel-art mode.
- **Color detail**: `quantize_colors = 256`.
- **Hue protection**: `hue_weight = 0.6` in Lumina's advanced conversion settings.
- **Batch mode**: use Lumina batch conversion when practical, even for a single image.
- **Output retention**: keep all intermediate files.
- **Run folder**: create a new subfolder under `output/` for every run.
- **3MF project settings**: preserve Lumina's generated settings; do not rewrite printer, layer-height, first-layer, or machine G-code fields.

## Output folder convention
Each run should create a new folder:
- `output/<timestamp>_<slug>/`

Expected contents (or the closest practical equivalent):
- `00_official_character_research.md` — required before generation for recognizable characters; record `not_applicable` for original/non-character subjects
- `01_source.png` — initial generated or provided source image
- `02_bg_removed.png` — transparent-background image after background removal
- `03_square_prepared.png` — square high-resolution canvas, horizontally centered and slightly raised subject
- `04_pixel_perfect.png` — low-resolution refined pixel art
- `05_pixel_preview_8x.png` — enlarged preview for visual inspection
- `06_lumina_2d_preview.png` — Lumina-generated 2D color preview, created before 3MF generation
- `07_lumina_batch_result.zip` — preserved Lumina batch archive (if batch endpoint returns zip)
- `08_<character-slug>.3mf` — extracted final 3MF named after the requested character
- `manifest.json` — metadata, parameters, and status summary
- `notes.txt` — optional diagnostics or manual observations

## Workflow

### 1) Prepare or generate the source image
If the user only gives a character name / textual description:
- Complete the mandatory official-character research gate and read `00_official_character_research.md` before constructing the prompt or calling image generation.
- Generate a source image first.
- Favor one character in a readable three-quarter pose with both eyes visible, horizontally centered and slightly above vertical center, minimal background, strong silhouette, readable accessories, and simple color blocks. Let the shoulders, hand, and prop remain naturally asymmetric.
- For a requested action, use the optional bundled action reference to keep the gesture and object readable without reducing the head's visual dominance. Adapt the interaction to the requested action instead of copying the example.
- Ask for clarification only when identity or composition is critically ambiguous.

If the user provides an image that already has the desired style and composition but identifies a local defect, use image editing and lock all unrelated geometry. Preserve the silhouette, head turn, face shape, neck width, shoulder line, crop, prop placement, palette, and pixel scale; change only the named defect.

Recommended generation style guidance:
- one character only
- natural upper-body portrait only: show the head, shoulders, and upper chest, without extending below the chest
- do not impose special hand, arm, or joint constraints; hands may appear naturally when the pose calls for them
- shift the composition upward by about 1–2 logical rows; make the head, hair, face, and identifying accessories the main visual mass
- keep a small top margin and a larger bottom margin; leave at least one clean background row below the completed bottom outline
- no text
- no busy background
- clean edges
- limited palette
- minimal gradients
- easy-to-read silhouette
- enough margin around the subject
- explicitly request an internal `24 × 24` logical canvas as a preventive undershoot, enlarged only with nearest-neighbor sampling and visibly large uniform cells
- align every silhouette step and color boundary to the same logical grid; do not create any feature or color region smaller than one logical cell
- use a one-logical-pixel pure-black exterior outline, stair-stepped contours, and very few interior details
- fully close the outline around the entire subject; make the lowest occupied row under the body a continuous black outline rather than skin, hair, or clothing color
- keep the face symbolic and readable; favor large hair, face, and clothing color regions over individual strands or texture
- default to a lively three-quarter head turn with both eyes visible; preserve asymmetric cheek, jaw, hair, and shoulder shapes so the pose does not flatten into a frontal portrait
- build both eyes from the same vertical pixel template: align their top/bottom rows and give both irises and pupils the same number of logical rows; perspective may make only the far eye up to one cell narrower
- keep the neck short and naturally broad where it meets the collar and shoulders; do not create a long narrow stalk under the head
- allow hair, glasses, hands, drinks, and props to overlap eye white, but not to shorten an iris/pupil or change either eye's top/bottom anchor rows
- use roughly 8–12 discrete colors with a few intermediate hues for layered-color demonstration
- if the generator emits a larger bitmap, depict a nearest-neighbor enlargement of the coarse logical design rather than adding detail, antialiasing, or intermediate-size cells

Generation acceptance gate:
- Inspect whether the generated image visually matches the bundled coarse, low-information references; do not trust the prompt claim alone.
- Compare its visible cell size and information density against the two bundled coarse-density references.
- Run Perfect Pixel auto-detection as a diagnostic before accepting the source. Prefer `44–60` cells per axis; treat any axis above `60` as too detailed and regenerate. Do not resample or force the grid.
- Reject and regenerate during the image-generation stage if it extends below the chest, uses fine hair strands or micro-texture, resembles a polished high-resolution illustration, lacks large readable color blocks, places the subject too low, or fails to make the head the dominant visual mass.
- Reject and regenerate if the subject touches the bottom canvas edge, the exterior outline is open, or the bottom-most occupied subject row is not a continuous pure-black baseline with background visible below it.
- Reject and regenerate if the default pose is flatly frontal or hides an eye in full profile, the eye centers occupy different logical rows, the eyes have different top/bottom rows, the irises or pupils use different row counts, the far eye is shorter or more than one cell narrower, or the pupils look in different directions. Ignore sclera-only occlusion when judging eye height.
- Reject and regenerate if the neck becomes a long narrow connector, the head appears detached from the shoulders, or eye correction changes the accepted pose, silhouette, face shape, neck, shoulders, crop, prop, palette, or pixel scale.
- Do not enforce a fixed grid or `65 × 65` later by resizing, sharpening, or adding detail. Let source generation determine the logical density.

### 2) Remove the background to transparency
This project prefers transparent PNGs before pixel refinement.

Use this two-stage strategy:
1. **Primary strategy**: subject/background segmentation or removal tool when available.
2. **Fallback strategy**: if segmentation is unavailable or poor, convert near-white / plain background regions to transparency.

Requirements:
- Preserve the main subject.
- Save the result as transparent PNG.
- If the original image already has alpha and it looks correct, keep it.

### 3) Force a square composition
The user chose a square workflow.
- Crop to the non-transparent subject bounds.
- Add padding so the subject has breathing room.
- Place the subject on a **square transparent canvas**.
- Keep the subject horizontally centered but slightly above vertical center; preserve or reapply the 1–2-logical-pixel upward bias.
- Preserve the complete pure-black exterior outline and at least one transparent row below its continuous bottom baseline.
- Save this prepared high-resolution square image before pixel refinement.

### 4) Run Perfect Pixel
Use Perfect Pixel as the low-resolution refinement step.
- Prefer automatic grid detection.
- Preserve the automatically detected grid without resizing it to a fixed target.
- If detection fails, return to image generation and create a clearer coarse-pixel source instead of forcing a downstream grid.
- If the detected result is not square, pad with transparent rows/columns after refinement to restore a square canvas while preserving the refined subject.
- Save the low-resolution image and an enlarged nearest-neighbor preview.

### 5) Cleanup before Lumina
Do light cleanup only.
- Remove isolated specks if obvious.
- Preserve transparency.
- If color count is extremely fragmented, simplify modestly, but avoid overprocessing.
- Keep implementation simple and deterministic.

### 6) Convert with Lumina
Use the local `Lumina-Layers/` repository in the project.

Preferred conversion behavior:
- Prefer **batch mode** for repeatability.
- Use a single-image batch when converting one image.
- Generate the Lumina 2D color preview first with the same LUT and conversion parameters; save it as a run artifact before generating the 3MF.
- If using the API path, read the current repo’s accepted parameter names rather than guessing.
- If a `color_mode` field is required by the current repo version, derive the correct accepted value from the repo/API for the chosen LUT instead of guessing.

Default conversion intent:
- square workflow with 65 mm physical output
- generate and retain the Lumina 2D preview before final conversion
- 1.2 mm backing
- double-sided structure
- no loop / no keychain hole
- chosen BambuLab PLA 4-color RYBW LUT
- pixel modeling mode
- quantize colors 256
- hue protection weight 0.6
- final pixel grid derived from Perfect Pixel automatic detection, with no forced target
- preserve Lumina's original 3MF project and slicing settings
- preserve full outputs

### 7) Save and summarize outputs
Always keep intermediates. Save a concise `manifest.json` that includes:
- run timestamp
- subject / character name
- official-character research status, brief path, and source URLs
- source image path
- final source-to-3MF parameter values
- detected pixel grid size
- final output grid and nominal millimeters per pixel
- Lumina method used (batch/api/core fallback)
- output file paths
- status / failure notes

## Decision rules
- Do not ask unnecessary questions if the user already provided enough information.
- If exact Lumina parameter enums differ from expectations, inspect the repo and adapt to the current implementation.
- Favor simple scripts and mature libraries over large custom frameworks.
- Keep code minimal and practical.
- Preserve intermediate files because this project is experimental and iterative.

## Suggested project-side scripts
If you are asked to implement the workflow in the project, create light-weight scripts such as:
- `tools/remove_background.py`
- `tools/prepare_square_canvas.py`
- `tools/refine_pixel.py`
- `tools/cleanup_pixel.py`
- `tools/lumina_batch.py`
- `tools/run_pipeline.py`

## References
Consult these when needed:
- [Coarse pixel-art generation prompt](references/generation-prompt.md)
- [Workflow details](references/workflow.md)
- [Default parameters](references/default-parameters.md)
- [Troubleshooting notes](references/troubleshooting.md)

## Example invocations
- “Generate Frieren and convert it into a layered 3MF.”
- “Use this uploaded character image, remove the background, pixel-refine it, and export a 3MF with the default BambuLab RYBW setup.”
- “Run the full pixel-art-to-3mf workflow and keep all intermediate files.”
