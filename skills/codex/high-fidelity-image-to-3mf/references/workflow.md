# Workflow

Use the values in [default-parameters.md](default-parameters.md); do not redefine them here.

## 1. Create the run and select the route

Create `output/<timestamp>_<slug>/` and select:

- `generate` for text-only creation;
- `reference-guided` for a new or edited target based on selected properties of an upload;
- `direct-conversion` when the upload itself is the target.

Preserve the original before editing, transcoding, cropping, background removal, or resizing. Record its path, extension, dimensions, alpha state, and hash when practical. Complete the research procedure in `SKILL.md` before generation or creative editing when applicable.

## 2. Create or accept the target

For generation or reference-guided work, follow [generation-prompt.md](generation-prompt.md). For direct conversion, make a lossless working copy and skip creative generation.

Inspect the target for requested identity and composition, accidental text/watermarks, duplicate subjects, anatomy or rendering artifacts, and adequate detail at the intended physical size. Regenerate or minimally edit generated targets that fail. For direct inputs, preserve the source and report limitations rather than redesigning it.

## 3. Prepare the image

Decide whether the background belongs to the print.

- Preserve an intentional scene or full-frame design.
- For an isolated subject, keep valid alpha or prefer segmentation.
- Use connected near-white removal only when safe for pale subject details.
- Pad meaningful content onto a square canvas instead of cropping it.
- Preserve smooth edges and alpha; resize only when necessary with a high-quality filter.
- Do not upscale merely to invent detail. Ask before generative enhancement of a direct input.

Save all preparation results as derivatives without overwriting the source.

## 4. Preview with Lumina

Resolve the configured LUT and its `color_mode` through the current API or `LUTManager`. Use the exact current parameter names and high-fidelity modeling enum.

Generate and save the 2D preview with the same image and color parameters intended for conversion. Compare it with the prepared image for subject loss, unwanted background, color collapse, muddy gradients, isolated noise, and major perceptual shifts. Change one justified variable at a time and regenerate the preview.

## 5. Convert with Lumina

Prefer batch conversion and preserve the returned ZIP before extracting the unique 3MF. If the API is unavailable, use the current core functions with `ModelingMode.HIGH_FIDELITY`. Do not reuse a wrapper that silently applies pixel mode or Perfect Pixel. Do not rewrite the generated 3MF metadata.

## 6. Artifacts and manifest

Keep the closest practical equivalent of:

- `00_official_character_research.md` when research is required
- `01_source.<ext>`
- `02_target_image.png`
- `03_bg_removed.png` when background removal is used
- `04_square_prepared.png`
- `05_lumina_2d_preview.png`
- `06_lumina_batch_result.zip`
- `07_<subject-slug>.3mf`
- `manifest.json`
- `notes.txt` when warnings need explanation

Record the route, subject, research status/sources, source provenance, target origin, preparation decisions, source/target/prepared/runtime dimensions, alpha state, resolved LUT/color mode, exact Lumina parameters, method used, artifact paths, status, and warnings. Return the prepared image, Lumina preview, 3MF, and manifest path.
