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
- Preserve all intermediate outputs and the raw batch archive, including Lumina's generated 3MF project settings
- Normalize only each extracted final 3MF to the pinned Bambu Lab A1 mini 0.4 mm profile after geometry finalization; never modify the `Lumina-Layers/` checkout

## Exact sizing gate

Treat the final cleaned and tight-cropped `04_pixel_perfect.png` dimensions as the only sizing source of truth. Do not use the generated-source resolution, semantic mask, temporary working grid, detected grid before cleanup, or a fixed millimeter target.

1. Preserve the final rectangular logical grid `W × H`; do not force it square.
2. Build two independent sizing plans: `2W × 2H` and `3W × 3H` integer Lumina cells.
3. Compute both Lumina-generation dimensions with decimal arithmetic: `width_mm = W × 0.84`, `height_mm = H × 0.84` for `2 × 2`; `width_mm = W × 1.26`, `height_mm = H × 1.26` for `3 × 3`.
4. Send the canonical decimal width through the API or core. The API accepts floating-point millimeters and derives height from image aspect ratio.
5. Before each conversion, simulate Lumina's current `int(target_width_mm / 0.42)` and aspect-ratio calculation. Continue only when the result exactly matches that variant's `2W × 2H` or `3W × 3H` plan.
6. Compensate only for binary-float representation at an integer boundary by nudging the transport width upward by the smallest representable float. Never round to a different Lumina cell count.
7. Fail if Lumina's configured pixel cell is not `0.42 mm`, or if exact integer mapping cannot be proven.
8. Only after the `3 × 3` 3MF exists, bake a centered XY `43 / 42` scale into every mesh vertex in every color part, then translate the complete result to preserve its original lower-left placement and prevent negative X/Y coordinates. Preserve Z coordinates, triangle topology, component assembly, material/extruder mapping, and all slicer settings. Mark the package so the operation is idempotent and fail on an ambiguous pre-existing build transform.

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
8. Leave the `2 × 2` geometry unchanged. Apply the verified centered XY vertex compensation to the final `3 × 3` model only. Keep the batch ZIP as the raw, unscaled and unnormalized Lumina archive.
9. Apply `tools/three_mf_a1mini_profile.py` to each extracted final 3MF. Keep the exact official A1 mini machine, 0.08 mm process, and Bambu PLA Basic preset IDs. Store the deliberate process changes as project-level overrides and list their keys only in element 0 of Bambu Studio's `different_settings_to_system` vector; size that vector as `process + N filaments + printer`, leaving every filament and printer element empty. Preserve only Lumina's dynamic colors, geometry, color/extruder mapping, and the completed XY compensation. Convert Lumina's H2D dual-nozzle flush data to the A1 mini single-nozzle representation by retaining exactly the first `N × N` matrix and one flush multiplier.

Treat both 3MFs as required final deliverables. Do not stop after the first succeeds, do not substitute manual slicer scaling for the baked `3 × 3` compensation, and do not ask the user to choose until both files and their exact final physical dimensions are available for comparison. Bambu Studio should remain at `100%` model scale; Arachne and `0.42 mm` line widths are embedded by the final profile normalization.

If the API path is unavailable, call the repository's core preview function first and then its core conversion logic. Inspect the current repository for accepted parameter and LUT names instead of guessing enum values.

The pinned profile starts from Bambu Studio 02.07.01.62's official `0.08mm Extra Fine @BBL A1M`, A1 mini 0.4 mm machine, current A1 mini machine G-code, and Bambu PLA Basic settings. Apply these deliberate overrides:

- `0.08 mm` initial layer; all relevant line widths `0.42 mm`
- Arachne, one wall loop, only one wall on the first layer, zero top/bottom shell layers
- 100% zig-zag sparse infill at `0°`; narrow internal solid infill detection disabled
- support disabled; automatic brim width `5 mm`
- single-extruder multimaterial and prime tower enabled
- prime tower width `170 mm`, prime-tower brim width `1 mm`, `X=5 mm`, `Y=160 mm`, prime-tower rib wall disabled

Keep the official A1 mini baseline for all unlisted machine, temperature, speed, acceleration, and filament parameters. This normalization belongs to the outer `pixel3mf` project only, so replacing or upgrading `Lumina-Layers/` cannot erase it.

## Manifest

Create `manifest.json` with:

- run timestamp and subject
- official-character research status, brief path, and source URLs
- source, background-removed, canvas-prepared, refined, and preview paths
- source, refined, temporary working, and tight export grids; removed outer-transparent cells; plus any explicitly requested square padding
- Lumina generation cell size and a keyed `2x2` / `3x3` record of cells per logical pixel, generation pitch, and final physical pitch
- for both variants, nominal Lumina-generation width and height, transport width, expected Lumina raster, simulated raster, and exact-mapping result
- for `3x3`, the XY scale factor, placement translation, before/after mesh bounds, vertex count, package hash, final `W × 1.29` / `H × 1.29` physical dimensions, unchanged-Z verification, and the fact that the retained batch archive is unscaled
- Lumina method, LUT, and conversion parameters
- A1 mini profile source, profile path, color count, preserved filament colors, prime-tower placement, project-settings hashes before/after, package hashes before/after, and whether normalization was applied
- both Lumina preview, archive, and final 3MF paths
- status, gate results, and failure notes

Keep `00_official_character_research.md`, `01_source.png`, all numbered intermediates, the manifest, and optional diagnostics in the run folder.
