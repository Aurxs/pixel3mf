# Stage 3 — Pixel Preparation and Refinement

Do not read this file until the source has passed Stage 2 or the user has explicitly accepted a reported limitation.

## Remove the background

Create `02_bg_removed.png` as a transparent PNG.

1. Keep existing correct alpha.
2. Otherwise prefer subject/background segmentation.
3. If segmentation is unavailable or poor and the background is plain, remove only near-white regions connected to the exterior background, using 8-connectivity so diagonal accessory/body gaps remain reachable.

Treat white RGB as foreground by default. Preserve enclosed white face, clothing, eye, highlight, and accessory regions. Before refinement, remove only high-confidence exterior-connected white background and record the cleanup method and counts. Keep ambiguous enclosed white regions, record them for later inspection, and continue without interrupting the pipeline.

## Prepare an aspect-preserving canvas

Create `03_canvas_prepared.png`.

- Crop to visible subject bounds.
- Add proportional breathing room on a transparent canvas without rescaling.
- Keep the subject horizontally centered and slightly above vertical center.
- Preserve the complete exterior outline and leave at least one transparent row below its continuous bottom baseline.
- Do not force the canvas to a square. Square output is optional and must be explicitly requested.

## Run Perfect Pixel

Create `04_pixel_perfect.png` and `05_pixel_preview_8x.png`.

- Prefer automatic grid detection.
- Preserve the automatically detected grid; do not resize to a fixed target.
- Save the raw detected grid and final output grid in metadata.
- If detection fails, reject the source and return through Stage 2 to a fresh Stage 1 generation. Do not choose a fixed fallback grid.
- Preserve a rectangular refined grid exactly. Do not add, duplicate, remove, or split a row or column merely to make it square.
- If square output was explicitly requested, pad only with complete transparent logical rows or columns and record the padding before physical-size calculation.
- Enlarge the preview with nearest-neighbor sampling only.

## Cleanup

- Remove obvious isolated foreground noise.
- On the refined logical grid, remove only near-white exterior components of at most two cells. Preserve interior white components and larger or otherwise ambiguous exterior white components, record them in metadata, and continue the pipeline without requesting an intermediate review.
- Preserve transparency, silhouette, palette, and detected grid.
- Avoid painting missing anatomy, rebuilding outlines, or applying complex heuristics after refinement.

Do not read Lumina settings until both refinement artifacts exist.
