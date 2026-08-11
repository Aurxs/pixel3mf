# Troubleshooting

## Common issues

### Background removal is poor
- Try segmentation first.
- If the background is plain or nearly white, use near-white-to-alpha fallback.
- Save diagnostics rather than silently discarding results.

### Perfect Pixel result is messy
- Ensure the source image has a simple background and readable silhouette.
- Re-run with the square-prepared image, not the raw source.
- If needed, tune only a small number of parameters.

### Generated pixel art is too detailed
- Fix the image-generation prompt first: request an internal 24 × 24 logical canvas as a preventive undershoot, enlarged only with nearest-neighbor sampling. The detector is not expected to return exactly 24 × 24.
- Load and explicitly match the cell scale of `reference-coarse-density-a.png` and `reference-coarse-density-b.png` without copying their content.
- Run Perfect Pixel auto-detection as a diagnostic. Treat either axis below 55 or above 72 cells as outside the target density and regenerate; do not resize.
- Require every contour and color boundary to align to the same grid, with no feature or color region smaller than one logical cell.
- Reject fine hair strands, micro-texture, dithering, smooth gradients, anti-aliasing, and polished illustration-style highlights.
- Do not force the image to a fixed grid later; regenerate until the source has the intended low-information style.

### Generated composition is too large or too detailed
- Default to a natural upper-body portrait that does not extend below the chest. Do not impose special hand or joint constraints.
- Shift the subject upward by about 1–2 logical rows and keep the face, hair, and signature accessories dominant.
- Leave a larger lower margin with at least one background row under the complete bottom outline.
- If the source is too detailed, regenerate with fewer and larger shapes instead of sharpening, resizing to a fixed grid, or upsampling.

### Eyes are vertically misaligned or look different in size
- Preserve the accepted three-quarter pose and all unrelated geometry. Treat alignment as a local raster edit, not a reason to redraw the head or body.
- Reuse one vertical eye template for both eyes: identical top/bottom anchor rows and identical iris/pupil row counts. Let perspective change width only; the far eye may be at most one logical cell narrower, never shorter.
- Allow hair, glasses, or props to overlap eye white. Judge eye height from eyelid anchors and iris/pupil row counts, not from the amount of visible sclera; occlusion must not crop the iris/pupil.
- Reject an edit that makes the face frontal or changes the silhouette, face/jaw shape, neck width, shoulders, crop, prop placement, palette, or pixel scale.

### Neck is too thin or detached from the shoulders
- Keep the neck short and naturally broad at its base, widening into the collar and shoulder mass rather than forming a long narrow stalk.
- Unless the character reference clearly requires otherwise, use a visible neck opening roughly one-quarter to one-third of the lower-face width and begin the collar within a few logical rows below the jaw.
- If the source was otherwise accepted, repair only the neck/collar junction and preserve the pose, face, silhouette, hands, prop, palette, and pixel density.

### Exterior or bottom outline is missing
- Regenerate with a one-logical-pixel pure-black outline that fully encloses the entire subject.
- Require the lowest occupied subject row to form a continuous black baseline, with at least one clean background row below it.
- Reject sources where skin, hair, clothing, or the outline touches the canvas bottom. Do not add the missing outline during downstream resizing or sharpening.

### Lumina rejects the LUT or a parameter
- Inspect the current `Lumina-Layers` repo version.
- Use `/api/lut/list` or the repo’s LUT manager to discover the exact accepted LUT naming.
- Do not hard-code uncertain enum values if the repo can be queried.

### Batch result contains a zip instead of direct 3MF
- Preserve the original zip.
- Extract the single 3MF and save it as `08_<character-slug>.3mf`.

### Final aspect ratio is not square
- The user explicitly chose a square workflow.
- Pad to square with transparency before Lumina.

### Printer or slicing settings need adjustment
- Keep the Lumina-generated 3MF settings unchanged during conversion.
- Inspect and adjust the printer model, layer heights, first layer, and machine G-code later in Bambu Studio.
