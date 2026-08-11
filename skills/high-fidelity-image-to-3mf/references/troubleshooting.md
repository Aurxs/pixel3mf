# Troubleshooting

## The target became pixel art

- Remove all logical-canvas, block-size, nearest-neighbor, coarse-grid, and limited-palette instructions.
- Do not load the pixel-art skill’s bundled style references.
- Skip Perfect Pixel and pixel-density detection entirely.
- Confirm the conversion request uses `modeling_mode=high-fidelity`, not `pixel`.

## An uploaded direct target was redesigned

- Restore the untouched `01_source.<ext>`.
- Rebuild derived artifacts without image generation or creative editing.
- Limit changes to lossless conversion, user-approved background removal, square padding, and necessary high-quality resizing.

## A reference image was treated as the direct target

- Return to the original upload.
- Identify the specific properties requested as references.
- Generate/edit a separate `02_target_image.png`; keep provenance explicit in the manifest.

## Background removal damages pale or fine details

- Prefer existing alpha.
- Tune segmentation before using color-key removal.
- Preserve intentional full-frame backgrounds.
- Avoid a near-white threshold when the subject contains white hair, clothing, glow, or highlights.
- Compare edge alpha against the original at high zoom.

## The source is too small

- Compare its dimensions with Lumina’s current processing target; this checkout uses roughly 10 px/mm in high-fidelity mode.
- Do not silently invent detail.
- For a generated/reference-guided target, regenerate at higher resolution.
- For direct conversion, disclose the limitation and ask before generative enhancement.

## The Lumina preview loses detail or shifts colors

- Confirm the intended LUT and detected `color_mode`.
- Confirm `quantize_colors=256`, `hue_weight=0.6`, and cleanup enabled.
- Inspect whether transparency or fine low-contrast features disappeared during preparation.
- Compare cleanup on/off only when isolated-pixel cleanup removes meaningful tiny features.
- Regenerate the preview after each single-variable change.

## Lumina rejects a modeling mode or parameter

- Inspect the current `Lumina-Layers/config.py`, API schemas, and route form fields.
- Use the exact API value `high-fidelity` or core enum `ModelingMode.HIGH_FIDELITY`.
- Resolve LUT naming through `/api/lut/list` or `LUTManager` instead of guessing.

## The existing project wrapper still outputs pixel geometry

- Do not call `tools/run_pipeline.py` or `tools/lumina_batch.py` unchanged; the current versions contain Perfect Pixel stages and/or `modeling_mode=pixel` defaults.
- Create a separate high-fidelity wrapper or add an explicit mode parameter while preserving the original pixel defaults.
- Verify both preview and final conversion metadata record `high-fidelity`.

## Batch returns a ZIP

- Preserve the original ZIP.
- Extract the unique `.3mf` and rename it for the requested subject.
- Record the archive member name and final path in the manifest.

## Printer or slicing settings need changes

- Preserve the Lumina-generated 3MF during conversion.
- Review printer, layer, first-layer, bed, filament, and G-code settings later in Bambu Studio.
