# Stage 3 — Perfect Pixel, Cleanup, Then Final Acceptance

Read after lightweight source preflight. Source gradients, antialiasing, extra colors and partial alpha are not reasons to skip this stage. Preserve `01_source.png` unchanged.

## 1. Choose necessary preparation

- For a generated source with real transparency, use its existing alpha directly. Skip semantic segmentation when the cutout already identifies the subject. Partial alpha is allowed as input here.
- For an opaque plain background needing removal, call the project's background tool with `isnet-general-use` explicitly; `auto` starts with the anime model. Keep RGB unchanged and retain semantic confidence in alpha until sampling.
- A painted checkerboard needs segmentation or a reviewed mask; Perfect Pixel cannot infer transparency from the checkerboard pattern. Do not globally erase pale colors or keep unwanted checkerboard squares as subject pixels.
- For intentional scenery/panel backgrounds, retain them as foreground content. Inspect windows, fur, white walls, snow and other light features according to the subject brief.
- A user binary mask takes precedence. For already-binary alpha, preserve it unless conservative hole repair is needed. Existing two-model repair requires agreement and protects the silhouette; unresolved components remain blocked before export.

If segmentation is necessary, retain the existing CPU-only subprocess limits: supported IS-Net models only, one session at a time, six OMP threads, 300-second timeout and 8 GiB default RSS limit. Do not load BiRefNet, PyTorch or GPU providers. Skip these dependencies entirely for a usable transparent cutout.

## 2. Run Perfect Pixel before judging pixel quality

Use `tools/refine_pixel.py --png-only`. This calls automatic grid detection with center sampling and no forced square/grid. The flag omits the old anime-source 60–85 density check; it does not resize to a chosen grid. Apply this refinement for both finished PNG and general-subject 3MF requests.

For generated transparent artwork, add `--binarize-alpha`: sampled logical cells with alpha >=128 become opaque, the others transparent. This happens after Perfect Pixel, not by thresholding or flattening the full-resolution original. Retain the original and metadata, including how many sampled cells had partial alpha. Do not assume alpha thresholding preserves every intended part; inspect the result.

For a semantic-confidence mask, leave alpha probabilities intact through sampling and use `finalize_pixel_grid(..., alpha_policy="semantic", background_rgb=<sampled background>)` for confidence/component decisions. If comparing an untouched source grid with a masked derivative, use the Python `refine_pixel` function's `expected_source_grid` check; a mismatch needs investigation, not a forced grid.

Save `03_working_grid.png` and `03_working_grid_preview_8x.png`. Failed automatic detection is a technical failure, not permission to force 24×24. A detected count different from the prompt target or outside 60–85 does not by itself fail this general workflow.

## 3. Finalize the actual logical grid

Use the existing `tools/cleanup_pixel.py` Python function `finalize_pixel_grid` to produce `04_pixel_perfect.png` and `05_pixel_preview_8x.png`, saving component diagnostics and the overlay.

- For a usable sampled binary cutout: `alpha_policy="preserve"`, `background_rgb=None`; preserve foreground cells and internal holes, with no RGB color-key or isolated-cell deletion.
- For semantic preparation: use the current confidence/component rules. Save ambiguous regions and stop before export unless a reviewed mask resolves them or the user explicitly accepts them.
- Tight-crop complete transparent outer rows/columns, including any working padding. Never crop part of a logical cell.
- Do not pad square unless requested. The final rectangular grid alone determines physical dimensions.
- Enlarge previews with nearest-neighbor only; save the logical image separately.

## 4. Formal quality acceptance — here, not on the raw generation

Inspect `04_pixel_perfect.png` and its enlarged preview against the source and subject brief:

- The requested subject, essential markings, intended framing and complete silhouette survive.
- The result is a readable coarse logical grid. Each cell has one color; no finer detail is inserted inside cells.
- Alpha is binary for a printable cutout; intentional subject whites and internal holes are preserved. An all-transparent or almost-erased subject does not pass.
- The actual background matches intent, and no unwanted checkerboard, detached background or unresolved mask component remains.

Do not reject solely for more than 6–8 colors, a detected grid different from 24×24, modest stepped shading across cells, or imperfections visible only in the raw generation. Perfect Pixel regularizes cells but does not guarantee a six-color palette or eliminate every tonal transition. Judge recognizability and pixel readability; do not invent stricter numerical aesthetic gates.

If the refined result still loses essential content or is unreadable, fix the smallest preparation issue or return to one fresh generation within the retry limit. Preserve failures and label their actual stage. Never silently quantize or force-resize to manufacture a pass.

For finished PNG, deliver the logical grid and preview now. For 3MF, record final acceptance in `manifest.json`, then read [lumina-conversion.md](lumina-conversion.md). Run the independent Lumina converter on the accepted grid; do not send it back through the legacy pipeline's raw-source gate or redetect it as a generated source.
