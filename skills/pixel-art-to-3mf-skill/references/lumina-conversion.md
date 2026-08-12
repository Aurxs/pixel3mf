# Stage 4 — Lumina Conversion and Finalization

Do not read this file until `04_pixel_perfect.png` and `05_pixel_preview_8x.png` exist.

## Conversion defaults

- Lumina generation cell: exactly `0.42 mm`; verify this against the local `PrinterConfig.NOZZLE_WIDTH` before conversion
- Required Lumina variants per refined logical pixel: exactly `2 × 2` and `3 × 3`; always export both
- Lumina generation pitches: `0.84 mm` for `2 × 2`, and `1.26 mm` for `3 × 3`
- Final physical pitches: `0.84 mm` for `2 × 2`; for `3 × 3`, bake an XY-only `43 / 42` (`102.380952%`) scale into the completed 3MF so its effective cell is `0.43 mm` and logical-pixel pitch is `1.29 mm`; never scale Z
- Physical canvases: derive both dynamically from the tight-cropped `export_grid` in `04_pixel_perfect.png` as `width × pitch` by `height × pitch`; never include temporary working padding
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

Treat the final cleaned and tight-cropped `04_pixel_perfect.png` dimensions as the only sizing source of truth. Do not use the generated-source resolution, semantic mask, temporary working grid, detected grid before cleanup, or a fixed millimeter target.

1. Preserve the final rectangular logical grid `W × H`; do not force it square.
2. Build two independent sizing plans: `2W × 2H` and `3W × 3H` integer Lumina cells.
3. Compute both Lumina-generation dimensions with decimal arithmetic: `width_mm = W × 0.84`, `height_mm = H × 0.84` for `2 × 2`; `width_mm = W × 1.26`, `height_mm = H × 1.26` for `3 × 3`.
4. Send the canonical decimal width through the API or core. The API accepts floating-point millimeters and derives height from image aspect ratio.
5. Before each conversion, simulate Lumina's current `int(target_width_mm / 0.42)` and aspect-ratio calculation. Continue only when the result exactly matches that variant's `2W × 2H` or `3W × 3H` plan.
6. Compensate only for binary-float representation at an integer boundary by nudging the transport width upward by the smallest representable float. Never round to a different Lumina cell count.
7. Fail if Lumina's configured pixel cell is not `0.42 mm`, or if exact integer mapping cannot be proven.
8. Only after the `3 × 3` 3MF exists, bake a centered XY `43 / 42` scale into every mesh vertex in every color part. Preserve Z coordinates, triangle topology, component assembly, material/extruder mapping, and all slicer settings. Mark the package so the operation is idempotent and fail on an ambiguous pre-existing build transform.

Do not send the final `W × 1.29` width to Lumina. Lumina would evaluate `int(target_width_mm / 0.42)` and eventually add columns, breaking the exact `3W × 3H` raster. The `1.29 mm` pitch is a final-geometry property only.

For example, a final `80 × 79` grid must export a `67.20 mm × 66.36 mm` `2 × 2` canvas with a `160 × 158` Lumina raster. The `3 × 3` path uses a `100.80 mm × 99.54 mm` Lumina-generation canvas with a `240 × 237` raster, then produces a final `103.20 mm × 101.91 mm` XY-compensated 3MF. Odd dimensions do not require padding.

## Conversion sequence

Use the local `Lumina-Layers/` checkout.

1. Build and validate the exact `2 × 2` and `3 × 3` sizing plans from the final refined grid.
2. Start or reuse the Lumina API server.
3. For each variant, call `/api/convert/preview` with its dynamic decimal width and the same final conversion parameters.
4. Save the returned PNGs as `06_lumina_2d_preview_2x2.png` and `06_lumina_2d_preview_3x3.png`.
5. Run batch conversion for each variant with the width used by its preview.
6. Preserve the returned archives as `07_lumina_batch_result_2x2.zip` and `07_lumina_batch_result_3x3.zip` when applicable.
7. Extract and name the models `08_<character-slug>_2x2.3mf` and `08_<character-slug>_3x3.3mf`.
8. Leave the `2 × 2` model unchanged. Apply the verified centered XY vertex compensation to the final `3 × 3` model only. Keep the batch ZIP as the raw, unscaled Lumina archive.

Treat both 3MFs as required final deliverables. Do not stop after the first succeeds, do not substitute manual slicer scaling for the baked `3 × 3` compensation, and do not ask the user to choose until both files and their exact final physical dimensions are available for comparison. Bambu Studio should remain at `100%` model scale with Arachne and `0.42 mm` line width.

If the API path is unavailable, call the repository's core preview function first and then its core conversion logic. Inspect the current repository for accepted parameter and LUT names instead of guessing enum values.

Do not rewrite printer model, layer height, first-layer, bed geometry, or machine G-code fields. Leave those for later review in Bambu Studio.

## Manifest

Create `manifest.json` with:

- run timestamp and subject
- official-character research status, brief path, and source URLs
- source, background-removed, canvas-prepared, refined, and preview paths
- source, refined, temporary working, and tight export grids; removed outer-transparent cells; plus any explicitly requested square padding
- Lumina generation cell size and a keyed `2x2` / `3x3` record of cells per logical pixel, generation pitch, and final physical pitch
- for both variants, nominal Lumina-generation width and height, transport width, expected Lumina raster, simulated raster, and exact-mapping result
- for `3x3`, the XY scale factor, before/after mesh bounds, vertex count, package hash, final `W × 1.29` / `H × 1.29` physical dimensions, unchanged-Z verification, and the fact that the retained batch archive is unscaled
- Lumina method, LUT, and conversion parameters
- both Lumina preview, archive, and final 3MF paths
- status, gate results, and failure notes

Keep `00_official_character_research.md`, `01_source.png`, all numbered intermediates, the manifest, and optional diagnostics in the run folder.
