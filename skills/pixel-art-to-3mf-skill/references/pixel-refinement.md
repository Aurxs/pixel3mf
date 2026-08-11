# Stage 3 — Pixel Preparation and Refinement

Do not read this file until the source has passed Stage 2 or the user has explicitly accepted a reported limitation.

## Remove the background

Create `02_bg_removed.png` as a transparent PNG.

1. Keep existing correct alpha.
2. Otherwise prefer subject/background segmentation.
3. If segmentation is unavailable or poor and the background is plain, convert near-white background regions to transparency.

Preserve the complete subject and save diagnostics when removal is imperfect.

## Prepare a square canvas

Create `03_square_prepared.png`.

- Crop to visible subject bounds.
- Add breathing room on a square transparent canvas.
- Keep the subject horizontally centered and slightly above vertical center.
- Preserve the complete exterior outline and leave at least one transparent row below its continuous bottom baseline.

## Run Perfect Pixel

Create `04_pixel_perfect.png` and `05_pixel_preview_8x.png`.

- Prefer automatic grid detection.
- Preserve the automatically detected grid; do not resize to a fixed target.
- Save the raw detected grid and final output grid in metadata.
- If detection fails, reject the source and return through Stage 2 to a fresh Stage 1 generation. Do not choose a fixed fallback grid.
- If the refined image is not square, pad the shorter side with transparent rows or columns without rescaling the subject.
- Enlarge the preview with nearest-neighbor sampling only.

## Cleanup

- Remove only obvious isolated noise.
- Preserve transparency, silhouette, palette, and detected grid.
- Avoid painting missing anatomy, rebuilding outlines, or applying complex heuristics after refinement.

Do not read Lumina settings until both refinement artifacts exist.
