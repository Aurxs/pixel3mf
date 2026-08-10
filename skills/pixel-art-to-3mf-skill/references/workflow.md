# Workflow Details

## 1. Source Image
If only a character name is given, create a source image first. Favor:
- one subject
- a natural upper-body portrait showing head, shoulders, and upper chest without extending below the chest
- horizontal centering with a 1–2-logical-row upward bias so the head and hair dominate the composition
- a readable three-quarter head turn by default, with both eyes visible; reserve full frontal or full profile for explicit requests
- three-quarter depth expressed through asymmetric cheek, jaw, nose, hair, and shoulders rather than a frontal face
- both eyes built from the same vertical pixel template, with identical top/bottom rows and identical iris/pupil row counts; the far eye may be at most one cell narrower, never shorter
- hair, glasses, or props may overlap sclera but must not shorten the iris/pupil or move either eye's anchor rows
- a short, naturally broad neck base flowing into the collar and shoulders rather than a long narrow connector
- no special restrictions on hands, arms, or joints; let the pose remain natural within the crop
- clear silhouette
- minimal background
- limited palette
- minimal shading
- no text
- readable accessories
- an explicitly requested internal 24 × 24 logical canvas, used as a preventive undershoot and enlarged only with nearest-neighbor sampling
- every contour and color boundary aligned to the same logical grid, with no feature smaller than one logical cell
- large uniform pixel blocks, a closed one-pixel pure-black exterior outline, stair-stepped contours, and very few interior details
- a continuous pure-black bottom-most subject row with at least one clean background row below it

If a provided image already has the desired composition and style but needs one local correction, edit it instead of regenerating it. Lock the crop, pixel scale, silhouette, head turn, face shape, neck width, shoulders, palette, hand/prop placement, and outline; change only the named defect.

When the textual request includes a clear action or handheld-object interaction, load `assets/reference-action-interaction.png` in addition to the standard style/density references. Use it only to guide action readability, hand/prop integration, and head-dominant three-quarter framing; do not inherit its subject, palette, clothing, hand side, exact pose, drink, or accessories.

After generation, inspect the image before accepting it and compare its cell scale against the bundled coarse-density references. Run Perfect Pixel auto-detection as a diagnostic: prefer approximately 44–60 detected cells per axis and regenerate when either axis exceeds 60. Values below 44 may be accepted if readable. Reject and regenerate when the composition extends below the chest, remains too detailed, sits too low, minimizes the head, defaults to a flat frontal pose, hides an eye, gives the eyes different top/bottom rows or different iris/pupil row counts, touches the canvas bottom, or lacks the closed black exterior outline and bottom baseline. Sclera-only occlusion is allowed. Do not force the logical grid, repair facial geometry, or paint a missing outline later.

## 2. Background Removal
Create `02_bg_removed.png` as transparent PNG.
- If the image already has good transparency, keep it.
- Otherwise run segmentation.
- If segmentation is unavailable or poor, convert near-white areas to transparency.

## 3. Square Preparation
Create `03_square_prepared.png`.
- Crop to visible subject bounds.
- Add some padding.
- Place the result on a square transparent canvas, horizontally centered and about 1–2 logical pixels above vertical center.
- Preserve the complete black exterior outline and leave at least one transparent row below the bottom baseline.

## 4. Perfect Pixel
Create `04_pixel_perfect.png` and `05_pixel_preview_8x.png`.
- Use automatic grid detection first.
- Save both the raw detected grid and final output grid in metadata.
- Preserve the automatic result instead of resizing to 24 × 24 or 65 × 65.
- If automatic detection fails, return to source generation instead of choosing a fixed fallback grid.
- If the refined image is not square, pad the shorter side with transparent rows/columns.

## 5. Cleanup
Keep cleanup light.
- Remove obvious isolated single-pixel noise.
- Preserve transparent background.
- Avoid complicated heuristics.

## 6. Lumina Conversion
Use the local `Lumina-Layers/` checkout.
Preferred path:
1. start or reuse Lumina API server
2. call `/api/convert/preview` for one image with the final conversion parameters
3. download and save the returned 2D PNG as `06_lumina_2d_preview.png`
4. call batch conversion for one image
5. download batch zip
6. preserve zip and extract final 3MF

Name the extracted 3MF after the requested character, for example `08_初音未来.3mf`, so multiple opened models remain distinguishable.

Fallback path:
- call the repo’s core preview function first, then the core conversion logic, if the API path is unavailable.

After conversion, keep Lumina's original 3MF project settings unchanged. Printer model, layer heights, first-layer settings, bed geometry, and machine G-code should be reviewed later in Bambu Studio.

## 7. Finalization
Create `manifest.json` with:
- timestamp
- subject
- source path
- prepared image path
- pixel-perfect image path
- refined grid size
- nominal pixel pitch in millimeters at the 65 mm target width
- Lumina parameter values
- Lumina 2D preview path and generation method
- final 3MF path
- status and notes
