# Stage 3 — Semantic Cutout and Pixel Refinement

Do not read this file until the source has passed the Stage 2 preflight or the user has explicitly accepted a reported limitation.

## Build the semantic mask

Create `02_semantic_mask.png` and `02_bg_removed.png` while preserving the source RGB.

1. Use only `isnet-anime` and `isnet-general-use`: use the anime model by default and the general model for an explicitly general subject or automatic enclosed-background adjudication. Do not load BiRefNet or PyTorch.
2. Run only one IS-Net session at a time in a subprocess using ONNX Runtime `CPUExecutionProvider`. Do not register CoreML, MPS, GPU, or ANE providers. Use six OMP threads, a 300-second timeout, and the configured 8 GiB default hard RSS limit.
3. For a fully opaque source, sample the background color from the source border. Exterior-connected matching background is always background; enclosed matching components require semantic confidence.
4. For a binary transparent source, never sample hidden RGB under transparent pixels and never run RGB color-key cleanup. Already-transparent pixels are immutable. `auto` conservatively audits only originally opaque internal cells; both IS-Net models must agree before a cell becomes a repair candidate, and a one-logical-cell boundary guard protects the original silhouette. Model disagreement is ambiguous and blocks export.
5. `preserve` keeps useful binary source Alpha exactly and skips both models. `repair` requires useful binary source Alpha. A user-supplied binary mask has highest precedence, is copied exactly, and skips model inference without changing source RGB.

Keep the model probability in alpha through Pixel Fine. Do not alpha-matte or soften source RGB.

## Run Pixel Fine on the source grid

Create `03_working_grid.png`, `04_pixel_perfect.png`, and `05_pixel_preview_8x.png`.

- Auto-detect the untouched source grid before semantic masking and require `60–85` cells per axis there only.
- Run Pixel Fine again with semantic confidence in alpha and require the detected grid to match the source preflight exactly.
- Preserve the rectangular grid and never force a fixed fallback grid.
- Add two complete transparent logical rows and columns on every side as temporary working padding. The configured value may change explicitly, but percentage padding is not used by the pipeline.
- For fully opaque sources, resolve background-colored logical components with foreground confidence `>= 0.80` and background confidence `<= 0.20`. In automatic mode, let the general model adjudicate every enclosed background-colored component that the anime model did not confidently reject; this includes high-confidence color/semantic conflicts such as a white gap called foreground by the anime model. A component whose adjudicating samples all remain below `0.50` is background; a component whose median is at least `0.80` is semantic foreground. Treat the unresolved interval as ambiguous.
- For binary transparent sources, remove only originally opaque internal cells for which both models report background confidence `<= 0.20`. Never add foreground into original transparency. Protect every originally opaque logical cell touching original transparency from automatic deletion. Do not run isolated-cell deletion on `preserve`, `repair`, or mask-override routes.
- If the two-model route leaves an ambiguous component, save `02_mask_review_overlay.png` and `02_mask_components.json` and stop before Lumina unless the user explicitly accepts it or supplies a corrected binary mask.
- Convert final alpha to exactly `0` or `255`. Isolated one-cell cleanup applies only to the fully opaque semantic route. Preserve semantic foreground whites such as eyes, hair, clothing, and highlights.

## Produce the export grid

- Tight-crop complete transparent rows and columns after cleanup. Preserve internal transparent holes.
- Remove all temporary working padding before physical-size calculation.
- Apply optional square padding only when explicitly requested; it is an intentional export-size change.
- Treat the tight `04_pixel_perfect.png` dimensions as `export_grid`, the only downstream sizing source.
- Enlarge the preview with nearest-neighbor sampling only.

Minor source blur, antialiasing, gradients, and near-identical colors pass when the final grid is stable, readable, binary-alpha, and free of unapproved ambiguous background components.

Do not read Lumina settings until the export artifact and preview pass this final gate.
