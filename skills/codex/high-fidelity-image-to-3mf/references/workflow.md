# Workflow Details

## 1. Route selection and provenance

- Select `generate` for a text-only request.
- Select `reference-guided` when the user asks to use an upload as a reference or requests a transformed/new target.
- Select `direct-conversion` when the user asks to convert the uploaded image itself.
- Save the original before editing, transcoding, cropping, background removal, or resizing.
- Record source path, extension, dimensions, alpha state, and a content hash when practical.

## 2. High-fidelity target

For generation or reference-guided work, create `02_target_image.png` after visual inspection. Preserve continuous detail, smooth contours, gradients, shading, and requested style. Do not impose a pixel grid, pixel-art palette, Perfect Pixel detection, or logical-density threshold.

For direct conversion, create `02_target_image.png` as a lossless working derivative without creative changes. If the input is already a suitable PNG, it may be copied unchanged.

## 3. Background handling

Decide whether the background belongs to the intended print.

- Preserve an intentional scene or full-frame design.
- For a single-subject plaque, prefer existing alpha or segmentation.
- Use a connected near-white fallback only for a plain removable background.
- Inspect pale hair, white clothing, highlights, transparency around fine edges, and interior holes before accepting removal.
- Save `03_bg_removed.png` only as a derived artifact; never overwrite the source.

## 4. Square preparation

Create `04_square_prepared.png`.

- Use the visible intended artwork bounds, not accidental transparent noise.
- Pad rather than crop meaningful content.
- Center according to the composition; preserve an intentional offset.
- Maintain alpha and smooth high-fidelity edges.
- Avoid resizing unless required. When resizing, use a high-quality resampler and inspect fine features afterward.
- Do not use nearest-neighbor or downsample to a logical grid.

## 5. Lumina preview

Resolve the LUT through `/api/lut/list` or `LUTManager`. Use the current accepted display name and detected color mode.

Generate the 2D preview with:

- `target_width_mm=65.0`
- `auto_bg=false` after explicit preparation
- `color_mode=<detected>`
- `modeling_mode=high-fidelity`
- `quantize_colors=256`
- `enable_cleanup=true`
- `hue_weight=0.6`

Save the preview as `05_lumina_2d_preview.png`. Inspect it at full view and zoomed view. Compare subject boundaries, important facial/identity details, gradients, and background against `04_square_prepared.png`.

## 6. Lumina conversion

Prefer a single-image call to `/api/convert/batch` with the same color and modeling parameters plus:

- `spacer_thick=1.2`
- `structure_mode=Double-sided`
- loop disabled

Preserve the returned ZIP as `06_lumina_batch_result.zip`, extract the unique 3MF, and rename it to `07_<subject-slug>.3mf`.

If the API is unavailable, call the current core functions with `ModelingMode.HIGH_FIDELITY`. Do not reuse a wrapper that silently hard-codes `modeling_mode=pixel`.

## 7. Manifest and handoff

Record:

- route and source provenance;
- source/target/prepared dimensions and alpha state;
- background and square-preparation actions;
- runtime Lumina processing dimensions;
- LUT name, path, and detected color mode;
- exact preview and conversion parameters;
- API, batch, or core method;
- preview, ZIP, and 3MF paths;
- warnings, failures, and any user-approved deviations.

Return the prepared high-fidelity image, Lumina preview, 3MF, and manifest.
