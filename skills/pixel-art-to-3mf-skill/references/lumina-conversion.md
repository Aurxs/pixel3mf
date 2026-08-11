# Stage 4 — Lumina Conversion and Finalization

Do not read this file until `04_pixel_perfect.png` and `05_pixel_preview_8x.png` exist.

## Conversion defaults

- Lumina pixel cell: exactly `0.42 mm`; verify this against the local `PrinterConfig.NOZZLE_WIDTH` before conversion
- Lumina cells per refined logical pixel: exactly `3 × 3`
- Refined logical-pixel pitch: `1.26 mm`
- Physical canvas: derive dynamically from the final `04_pixel_perfect.png` grid as `width × 1.26 mm` by `height × 1.26 mm`
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
2. Set the expected Lumina raster to `3W × 3H` integer cells.
3. Compute nominal dimensions with decimal arithmetic: `width_mm = W × 1.26`, `height_mm = H × 1.26`.
4. Send the canonical decimal width through the API or core. The API accepts floating-point millimeters and derives height from image aspect ratio.
5. Before conversion, simulate Lumina's current `int(target_width_mm / 0.42)` and aspect-ratio calculation. Continue only when the result is exactly `3W × 3H`.
6. Compensate only for binary-float representation at an integer boundary by nudging the transport width upward by the smallest representable float. Never round to a different Lumina cell count.
7. Fail if Lumina's configured pixel cell is not `0.42 mm`, or if exact integer mapping cannot be proven.

For example, a final `80 × 79` grid must use a nominal `100.80 mm × 99.54 mm` canvas and produce a `240 × 237` Lumina raster. Odd dimensions do not require padding.

## Conversion sequence

Use the local `Lumina-Layers/` checkout.

1. Build and validate the exact sizing plan from the final refined grid.
2. Start or reuse the Lumina API server.
3. Call `/api/convert/preview` with the dynamic decimal width and final conversion parameters.
4. Save the returned PNG as `06_lumina_2d_preview.png`.
5. Run batch conversion with the identical dynamic width.
6. Preserve the returned archive as `07_lumina_batch_result.zip` when applicable.
7. Extract and name the final model `08_<character-slug>.3mf`.

If the API path is unavailable, call the repository's core preview function first and then its core conversion logic. Inspect the current repository for accepted parameter and LUT names instead of guessing enum values.

Do not rewrite printer model, layer height, first-layer, bed geometry, or machine G-code fields. Leave those for later review in Bambu Studio.

## Manifest

Create `manifest.json` with:

- run timestamp and subject
- official-character research status, brief path, and source URLs
- source, background-removed, canvas-prepared, refined, and preview paths
- detected, refined, and final rectangular pixel grids, plus any explicitly requested square padding
- Lumina cell size, cells per logical pixel, and logical-pixel pitch
- nominal decimal width and height, transport width, expected Lumina raster, simulated raster, and exact-mapping result
- Lumina method, LUT, and conversion parameters
- Lumina preview, archive, and final 3MF paths
- status, gate results, and failure notes

Keep `00_official_character_research.md`, `01_source.png`, all numbered intermediates, the manifest, and optional diagnostics in the run folder.
