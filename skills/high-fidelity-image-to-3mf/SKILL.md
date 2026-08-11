---
name: high-fidelity-image-to-3mf
description: Turn a text-described subject or an uploaded high-fidelity raster image into a printable layered 3MF with the local Lumina-Layers checkout. Before any image generation or editing of a recognizable character, mascot, or branded figure, research official character sources and use that brief as the visual identity authority. Use when Codex must generate a detailed non-pixel source image, use an uploaded normal/high-fidelity image as a visual reference for a new target image, directly prepare an uploaded high-fidelity image as the final conversion input, or convert any of those inputs with Lumina High-Fidelity mode while retaining intermediate artifacts. Default to a 65 mm square, BambuLab PLA 4-color RYBW LUT, 1.2 mm backing, double-sided structure, no loop, modeling_mode high-fidelity, quantize_colors 256, hue_weight 0.6, cleanup enabled, and batch conversion when practical.
---

# High-Fidelity Image to 3MF

Run an end-to-end **text or uploaded image → high-fidelity target image → Lumina preview → layered 3MF** workflow. Preserve continuous-tone detail, antialiased contours, gradients, illustration or photographic rendering, and natural high-resolution geometry. Never introduce a logical pixel grid or run Perfect Pixel.

## Required input

Accept at least one of:

- a subject, character name, or scene description;
- an uploaded/local image to use as a visual reference; or
- an uploaded/local image to convert directly.

Infer the route from the request:

1. **Generate** — create a new high-fidelity target from text.
2. **Reference-guided** — use the uploaded image to guide identity, style, composition, pose, or another named property, then generate or edit a distinct target image.
3. **Direct conversion** — treat the uploaded image itself as the target. Preserve the original and make only conversion-required derived copies.

Treat “use this as a reference” as reference-guided. Treat “convert this image” or “turn this into a 3MF” as direct conversion. Ask one concise question only when the intended route is genuinely ambiguous and choosing incorrectly would materially change the image.

Read [generation-prompt.md](references/generation-prompt.md) when generating or editing an image. Read [workflow.md](references/workflow.md) before executing the image-to-3MF pipeline. Use [default-parameters.md](references/default-parameters.md) for exact defaults and [troubleshooting.md](references/troubleshooting.md) after a failed acceptance check or conversion.

## Mandatory official-character research gate

Before every image-generation or image-editing call in this skill—including the first target, a retry, a repair, or a variant—complete this gate. Direct conversion and deterministic local processing do not count as image generation and do not need a new search.

- For a named or recognizable anime, game, cartoon, film, historical, mascot, or branded character, use web search first. Use only the official character page, publisher/developer/franchise site, official guide, press kit, or another first-party source. Do not substitute a secondary source unless the user explicitly allows it.
- Search narrowly for the canonical identity, for example: `<character name> official character profile` and `<character name> official site`. Do not generate while the search is pending.
- Save `00_official_character_research.md` in the run folder before generation. Record the canonical name/version, 1–4 official source URLs (prefer 2–4 when available), verified visual attributes (face/hair/body, clothing, palette, props, motifs), and an explicit `Verified facts` versus `Inferences` distinction. Treat the brief as the identity source of truth for the prompt, but do not copy logos, readable marks, slogans, or long source text.
- If the request is an original/non-character subject, still evaluate the gate and record `official_character_research_status=not_applicable`; never invent an official profile. If a named character has no reliable official source or the identity is ambiguous, stop before generation and ask for an approved reference or permission to proceed without official data.
- Carry the research file path and source URLs into `manifest.json` as `official_character_research_path` and `official_character_sources`.

## Non-negotiable behavior

- Keep pixel-art-specific processing and defaults separate; this is a separate workflow.
- Default every newly generated target to high-fidelity raster art, not pixel art.
- Accept ordinary detailed photos, illustrations, renders, and character art as references or direct inputs.
- Preserve a direct-conversion source byte-for-byte in the run folder before creating derived files.
- Do not use Perfect Pixel, nearest-neighbor pixel enlargement, logical-cell detection, coarse-grid acceptance, forced pixel density, or pixel cleanup scripts.
- Do not route the final image through the project’s current pixel pipeline unchanged. `tools/run_pipeline.py` and `tools/lumina_batch.py` contain pixel-specific stages/defaults in this checkout.
- Set Lumina `modeling_mode` to the exact API value `high-fidelity`. For core calls, use `ModelingMode.HIGH_FIDELITY`.
- Generate and inspect the Lumina 2D color preview before generating the 3MF.
- Preserve Lumina’s generated 3MF project and slicing settings.

## Fixed defaults

Unless the user overrides them, use:

- square output composition;
- physical size `65 mm × 65 mm`;
- backing thickness `1.2 mm`;
- structure `Double-sided`;
- hanging loop disabled;
- LUT file `Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy` from `Lumina-Layers/lut-npy预设/bambulab/`;
- the LUT’s detected `color_mode` rather than a guessed value; this LUT is currently `RYBW`;
- `modeling_mode = high-fidelity`;
- `quantize_colors = 256`;
- `hue_weight = 0.6`;
- isolated-pixel cleanup enabled in Lumina;
- Lumina batch conversion when practical, including a one-image batch;
- all intermediate outputs retained in a new timestamped run folder.

The current Lumina checkout processes high-fidelity bitmaps at `10 px/mm`, so a 65 mm square becomes approximately `650 × 650` processing pixels. Verify this against the current checkout and record the actual dimensions; do not hard-code it as a permanent upstream resize rule.

## Output folder

Create `output/<timestamp>_<slug>/` for every run. Keep the closest practical equivalent of:

- `00_official_character_research.md` — required before generation for recognizable characters; record `not_applicable` for original/non-character subjects;
- `01_source.<ext>` — untouched upload or original generated source;
- `02_target_image.png` — accepted high-fidelity target after any requested generation/edit;
- `03_bg_removed.png` — transparent-background derivative when removal is appropriate;
- `04_square_prepared.png` — final square high-fidelity image passed to Lumina;
- `05_lumina_2d_preview.png` — Lumina LUT-matched preview;
- `06_lumina_batch_result.zip` — preserved batch archive;
- `07_<subject-slug>.3mf` — extracted final 3MF;
- `manifest.json` — route, provenance, parameters, dimensions, outputs, and status;
- `notes.txt` — optional visual QA or failure notes.

Do not overwrite the uploaded source. If a stage is unnecessary, preserve the numbering and record that the prior artifact was reused or copied.

## Workflow

### 1. Select the input route

Record `generate`, `reference-guided`, or `direct-conversion` in the manifest.

- For **generate**, create a detailed target image from the user’s description.
- For **reference-guided**, inspect the uploaded image and use only the properties requested by the user. Preserve identity and requested visual cues without assuming that every detail must be copied.
- For **direct conversion**, skip image generation and style transfer. Copy the original into the run folder and treat it as the target.

For **generate** and **reference-guided**, complete the mandatory official-character research gate and read `00_official_character_research.md` before constructing the prompt or calling image generation. For **direct conversion**, record that the gate was not applicable because no image was generated.

### 2. Create or accept the target image

For generated or reference-guided targets:

- default to a high-resolution, high-fidelity raster image;
- favor one readable subject, a clean silhouette, deliberate composition, and no text unless requested;
- retain smooth curves, small features, gradients, shading, and antialiasing where they support the requested appearance;
- avoid pixel-art language, block grids, nearest-neighbor scaling, deliberate low resolution, dithering intended to imitate pixels, or an arbitrary limited palette;
- generate at sufficient resolution for inspection and for Lumina’s intended physical output.

For direct conversion:

- preserve the visual content, crop, colors, detail, and rendering style;
- make no creative edits unless the user requests them;
- do not regenerate merely because the image is not square or lacks transparency.

### 3. Inspect the target

Use image inspection before conversion. Confirm:

- the requested subject and composition are correct;
- the target is genuinely detailed/non-pixel unless the user intentionally supplied mixed media;
- important features remain readable near the intended `65 mm` physical size;
- no accidental text, watermark, duplicate subject, broken anatomy, or generation artifact is present;
- the resolution is adequate for the current Lumina processing size.

If a generated/reference-guided image fails, regenerate it from scratch by default. Do not use the rejected generated image as an edit target, explicit reference, or recent-image context. Edit only a user-provided source when the user explicitly requests a local correction. If a direct input has a quality limitation, report it and preserve the source; do not silently redesign it.

### 4. Handle background and square preparation

Prefer transparent PNG for a single-subject plaque, but preserve an intentional full-frame background.

- Keep correct existing alpha.
- Otherwise use segmentation when background removal matches the user’s intent.
- Use a plain/near-white connected-background fallback only when safe.
- Never erase pale subject details merely to force transparency.
- Crop and pad a derived copy to a square canvas for the default square workflow.
- Preserve high-fidelity edges and alpha. Use a high-quality resampler if resizing is unavoidable; never use nearest-neighbor to create a pixelated look.
- Do not upscale solely to invent detail. If the source is undersized, either accept the limitation with a note or ask before applying generative enhancement.

### 5. Generate the Lumina 2D preview

Use the local `Lumina-Layers/` checkout. Query `/api/lut/list` or `LUTManager` to resolve the exact LUT display name and detected `color_mode`.

Call the current preview API/core path using the prepared image and the fixed defaults. Pass `modeling_mode=high-fidelity`, `quantize_colors=256`, `enable_cleanup=true`, and `hue_weight=0.6`. Save the returned preview before 3MF generation.

Inspect the preview for subject loss, unwanted background, color collapse, muddy gradients, isolated color noise, or a large perceptual shift. Change only the smallest justified parameter or image-preparation choice, then regenerate the preview.

### 6. Convert with Lumina High-Fidelity mode

Prefer `/api/convert/batch` for repeatability. A single-image batch is acceptable. If the API path is unavailable, use the current core conversion functions with `ModelingMode.HIGH_FIDELITY`.

Read accepted parameter names and enums from the current checkout instead of guessing. Preserve the batch ZIP and extract its 3MF. Keep `add_loop` disabled and retain all other fixed defaults.

Do not rewrite printer model, nozzle, layer height, first layer, bed geometry, filament mapping, or machine G-code fields inside the 3MF. Let the user inspect print settings later in Bambu Studio.

### 7. Finalize and summarize

Write `manifest.json` with:

- timestamp and subject;
- official-character research status, brief path, and source URLs;
- selected input route;
- original source path and hash when practical;
- whether the target was generated, reference-guided, edited, or directly reused;
- background and square-preparation decisions;
- source, target, prepared, and Lumina processing dimensions;
- resolved LUT name/path and detected `color_mode`;
- all Lumina parameters, including `modeling_mode=high-fidelity`;
- preview, ZIP, and final 3MF paths;
- API/batch/core method used;
- status, warnings, and failure details.

Return the final 3MF, the Lumina preview, the prepared target image, and the manifest path.

## Implementation guidance

If asked to implement project-side automation, create a separate high-fidelity entry point or parameterize shared utilities without changing the pixel workflow’s defaults. Prefer names such as:

- `tools/prepare_high_fidelity_image.py`
- `tools/lumina_high_fidelity_batch.py`
- `tools/run_high_fidelity_pipeline.py`

Reuse safe generic behavior such as source copying, background segmentation, square padding, API startup, LUT discovery, ZIP preservation, and manifest handling. Remove Perfect Pixel, logical-grid detection, nearest-neighbor preview, pixel-only cleanup, and hard-coded `modeling_mode=pixel` from the high-fidelity path.

## Example invocations

- “Generate a high-detail illustration of Frieren and convert it to a layered 3MF.”
- “Use this uploaded portrait as the identity and style reference, create a clean high-fidelity target, then export a 3MF.”
- “Convert this uploaded high-resolution image directly; do not redraw it.”
- “Run the high-fidelity image-to-3MF workflow with the default RYBW setup and keep every intermediate file.”
