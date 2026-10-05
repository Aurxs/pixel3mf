# Prepare an existing source

Resolve `PYTHON` and the project’s `TOOLS_DIR` using [runtime.md](runtime.md). Use a new output directory. The tool retains the original and a lossless PNG derivative.

For raw or enlarged pixel artwork:

```bash
"$PYTHON" "$TOOLS_DIR/prepare_source.py" /absolute/source.png /absolute/run/prepared
```

This calls Perfect Pixel with automatic grid detection, center sampling and no forced square. It thresholds sampled alpha at 128 only after refinement, tight-crops fully transparent outer rows/columns and saves `04_pixel_perfect.png` plus `05_pixel_preview_8x.png`. A detected grid different from the prompt is not an automatic failure; judge the refined result.

A known final logical grid skips this tool and goes to `bead_pattern.py`. If it needs preparation, use `--logical` to avoid redetection and preserve its existing canvas. Logical input must have binary alpha.

## Background choices

- Usable existing transparency: preserve it; no segmentation.
- Intentional opaque background: preserve it; no segmentation.
- Opaque background explicitly needing removal: add `--remove-background`. The bundled IS-Net worker keeps source RGB and passes semantic confidence through cell sampling. Ambiguous components block acceptance; inspect the saved diagnostic overlay.
- A reviewed foreground mask: add `--mask /absolute/mask.png`. It must be binary and match the EXIF-oriented source dimensions. It takes precedence over segmentation.
- Never globally erase white. White fur, eyes, clothing and intentional scenery remain opaque.
- A painted checkerboard is not transparency. Remove it with an appropriate reviewed mask/segmentation or regenerate a fresh source within the retry limit.

If an opaque background matches the subject outline (especially black on black), color-connected background removal cannot distinguish that outline from the backdrop. Inspect the original, high-resolution mask and sampled grid separately; a thin surviving edge can disappear during center sampling. Prefer an earlier source with usable alpha or a clearly separated background, or an explicitly reviewed mask. Do not globally dilate the silhouette or restore all dark/low-alpha background pixels.

After semantic removal, inspect the complete contour, pale subject areas and holes. If alpha was already usable, omit removal rather than running a second mask. Raw partial alpha is supported by the normal refinement route; the optional semantic-removal route requires opaque/binary input or a reviewed mask.

## Acceptance

When reusing a later local-repair version, compare the full silhouette and outline with the earlier accepted artwork as well as checking the requested repair. A newer timestamp or corrected mouth is not evidence that background removal preserved the rest of the drawing. Reject unintended outline loss; prefer the intact source plus the authorized local correction over an unreviewed global thickening.

Review the final enlarged preview against the original subject brief. Check recognition, complete silhouette, coarse readable cells, background intent and alpha. The tool labels output `needs_visual_review`, never automatically accepted. Keep prep metadata and failed candidates. No 45–80 density gate, Lumina sizing or 3MF cleanup rules apply.

Shrinking an accepted grid changes the design. If the user requires a smaller target, use [compression.md](compression.md) to prepare a separate derivative, preserve aspect ratio and the exterior outline, inspect the lost detail and record the change. The chart renderer itself only offers non-destructive padding through `--canvas`; shrinking belongs in that explicit compression stage.

## Source-supported narrow connections (optional)

Check four-neighbor connectivity separately from eight-neighbor contact: diagonally touching beads may not form an ironable bridge. A disconnected result does not authorize joining all decorations. Compare it with the actual source mask before changing occupancy. Do not lower the whole alpha threshold to recover a bridge; low-alpha background RGB may be black noise.

For a sampling-induced diagonal break with verifiable source evidence, `tools/beads/bridge_pixels.py` can propose minimal one-cell repairs to a saved bead project:

```bash
"$PYTHON" "$TOOLS_DIR/bridge_pixels.py" /absolute/reviewed-project.json \
  /absolute/sampling-evidence.json /absolute/new-bridged-project.json --max-additions 4
```

Evidence uses `pixel-sampling-evidence/v1`: actual source canvas/reference grid paths and their SHA256 hashes, exact nonuniform `x_edges`/`y_edges`, `alpha_threshold: 128`, and recorded `reference_differences`. Replay must reproduce the reference; only documented near-white edge removals matching `manifest_cleanup.removed_edge_white_pixels` are allowed. The project occupancy must match the reference, or its recorded non-resampled `uncompressed_crop`. Keep the original sampling bounds; do not infer them from image dimensions. The tool handles a final Perfect Pixel boundary extrapolated beyond the canvas by clipping its source footprint.

The opt-in rule only considers original diagonal contacts between different four-connected components. A candidate source patch must contain a four-connected foreground path crossing both neighboring sides and reaching both source endpoints locally. At least 15% of the patch must support that path; equally plausible corners (less than two percentage points apart) are left for review. It inserts at most the requested budget, uses an existing adjacent color code, freezes every old cell and never chains across wider gaps. No character coordinates or new color codes are prescribed.

For a resized board, first reproduce its complete mapping from the retained original and record the composition of resize/crop offsets with the actual sampling boundaries. The CLI rejects unproven resizing; the core `repair_bridges` function can accept boundaries from a separately verified transform. Missing evidence means stop that automatic repair and report the gap, not guess a connection.

Inspect the source path, proposed bridge and face before accepting. Confirm old occupied cells and color codes are identical, the palette union does not grow, and only the recorded bridge count changes bead totals. Keep the current reviewed palette (including any justified count above 18). Re-render the new project with `bead_pattern.py` to recompute materials, connected components and both mirror charts. A proposed repair remains `needs_visual_review`; it is never an automatic global connectivity pass.
