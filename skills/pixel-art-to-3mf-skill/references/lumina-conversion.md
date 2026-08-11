# Stage 4 — Lumina Conversion and Finalization

Do not read this file until `04_pixel_perfect.png` and `05_pixel_preview_8x.png` exist.

## Conversion defaults

- Physical size: `75 mm × 75 mm`
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

## Conversion sequence

Use the local `Lumina-Layers/` checkout.

1. Start or reuse the Lumina API server.
2. Call `/api/convert/preview` with the final conversion parameters.
3. Save the returned PNG as `06_lumina_2d_preview.png`.
4. Run batch conversion for the refined image.
5. Preserve the returned archive as `07_lumina_batch_result.zip` when applicable.
6. Extract and name the final model `08_<character-slug>.3mf`.

If the API path is unavailable, call the repository's core preview function first and then its core conversion logic. Inspect the current repository for accepted parameter and LUT names instead of guessing enum values.

Do not rewrite printer model, layer height, first-layer, bed geometry, or machine G-code fields. Leave those for later review in Bambu Studio.

## Manifest

Create `manifest.json` with:

- run timestamp and subject
- official-character research status, brief path, and source URLs
- source, background-removed, square-prepared, refined, and preview paths
- detected and final pixel grids
- nominal millimeters per pixel at the physical target
- Lumina method, LUT, and conversion parameters
- Lumina preview, archive, and final 3MF paths
- status, gate results, and failure notes

Keep `00_official_character_research.md`, `01_source.png`, all numbered intermediates, the manifest, and optional diagnostics in the run folder.
