# Stage 4 — Lumina Conversion and Finalization

Do not read this file until `04_pixel_perfect.png` and `05_pixel_preview_8x.png` exist.

## Conversion defaults

- Lumina pixel cell: exactly `0.42 mm`; verify this against the local `PrinterConfig.NOZZLE_WIDTH` before conversion
- Required Lumina variants per refined logical pixel: exactly `2 × 2` and `3 × 3`; always export both
- Refined logical-pixel pitches: `0.84 mm` for `2 × 2`, and `1.26 mm` for `3 × 3`
- Physical canvases: derive both dynamically from the same final `04_pixel_perfect.png` grid as `width × pitch` by `height × pitch`
- Backing thickness: `1.2 mm`
- Structure: `Double-sided`
- Hanging loop: disabled
- LUT: `Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy` from Lumina's `lut-npy预设/bambulab/` presets
- Modeling mode: pixel
- `quantize_colors = 256`
- `hue_weight = 0.6`
- Preserve the automatically refined grid without forcing a target grid
- Prefer batch conversion, including a single-image batch
- Preserve all intermediate outputs and Lumina's generated 3MF project settings

## Exact sizing gate

Treat the final cleaned `04_pixel_perfect.png` dimensions as the only sizing source of truth. Do not use the generated-source resolution, pre-refinement canvas, detected grid before cleanup, or a fixed millimeter target.

1. Preserve the final rectangular logical grid `W × H`; do not force it square.
2. Build two independent sizing plans: `2W × 2H` and `3W × 3H` integer Lumina cells.
3. Compute both nominal dimensions with decimal arithmetic: `width_mm = W × 0.84`, `height_mm = H × 0.84` for `2 × 2`; `width_mm = W × 1.26`, `height_mm = H × 1.26` for `3 × 3`.
4. Send the canonical decimal width through the API or core. The API accepts floating-point millimeters and derives height from image aspect ratio.
5. Before each conversion, simulate Lumina's current `int(target_width_mm / 0.42)` and aspect-ratio calculation. Continue only when the result exactly matches that variant's `2W × 2H` or `3W × 3H` plan.
6. Compensate only for binary-float representation at an integer boundary by nudging the transport width upward by the smallest representable float. Never round to a different Lumina cell count.
7. Fail if Lumina's configured pixel cell is not `0.42 mm`, or if exact integer mapping cannot be proven.

For example, a final `80 × 79` grid must export both a nominal `67.20 mm × 66.36 mm` canvas with a `160 × 158` Lumina raster, and a nominal `100.80 mm × 99.54 mm` canvas with a `240 × 237` Lumina raster. Odd dimensions do not require padding.

## Conversion sequence

Use the local `Lumina-Layers/` checkout.

1. Build and validate the exact `2 × 2` and `3 × 3` sizing plans from the final refined grid.
2. Start or reuse the Lumina API server.
3. For each variant, call `/api/convert/preview` with its dynamic decimal width and the same final conversion parameters.
4. Save the returned PNGs as `06_lumina_2d_preview_2x2.png` and `06_lumina_2d_preview_3x3.png`.
5. Run batch conversion for each variant with the width used by its preview.
6. Preserve the returned archives as `07_lumina_batch_result_2x2.zip` and `07_lumina_batch_result_3x3.zip` when applicable.
7. Extract and name the final models `08_<character-slug>_2x2.3mf` and `08_<character-slug>_3x3.3mf`.

Treat both 3MFs as required final deliverables. Do not stop after the first succeeds, do not substitute slicer scaling for either variant, and do not ask the user to choose until both files and their exact physical dimensions are available for comparison.

If the API path is unavailable, call the repository's core preview function first and then its core conversion logic. Inspect the current repository for accepted parameter and LUT names instead of guessing enum values.

Do not rewrite printer model, layer height, first-layer, bed geometry, or machine G-code fields. Leave those for later review in Bambu Studio.

## Manifest

Create `manifest.json` with:

- run timestamp and subject
- official-character research status, brief path, and source URLs
- source, background-removed, canvas-prepared, refined, and preview paths
- detected, refined, and final rectangular pixel grids, plus any explicitly requested square padding
- Lumina cell size and a keyed `2x2` / `3x3` record of cells per logical pixel and logical-pixel pitch
- for both variants, nominal decimal width and height, transport width, expected Lumina raster, simulated raster, and exact-mapping result
- Lumina method, LUT, and conversion parameters
- both Lumina preview, archive, and final 3MF paths
- status, gate results, and failure notes

Keep `00_official_character_research.md`, `01_source.png`, all numbered intermediates, the manifest, and optional diagnostics in the run folder.
