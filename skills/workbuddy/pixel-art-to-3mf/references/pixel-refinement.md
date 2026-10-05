# Stage 3 — Semantic Cutout and Pixel Refinement

Do not read this file until the source has passed the Stage 2 preflight. A density-gate failure requires a new or explicitly authorized edited source; acknowledgement alone does not bypass the gate.

## WorkBuddy cutout selection

For a fully opaque, uniform white-background pixel source with a closed dark outline and unambiguous enclosed whites (eyes or highlights), use the wrapper's existing `--background-method white` mode. It removes only exterior-connected near-white background and preserves enclosed whites. Do not use it when enclosed background holes require semantic adjudication; use the semantic path below in that case.

An ambiguous semantic result is not evidence that enclosed whites should be filled. Never switch to `white` solely to bypass an ambiguity failure when true enclosed background holes exist. Review each relevant component against the source; a high-confidence foreground label can still be wrong. Apply an explicitly reviewed source-resolution binary mask, preserve the source RGB and hash, and record removed and preserved regions. Avoid repeatedly recalibrating the same region after a concrete visual-review decision.

Always compare the final pixel preview with the accepted source. Semantic probability can delete real colored parts even when the ambiguous-background count is zero. Missing shoulders, contour or baseline are a delivery failure. Preserve the original run; for a source meeting the simple-white conditions above, re-export the exact accepted source in a new direct run with `--background-method white`. Never turn a rejected generation into a direct run to bypass Stage 2.

## Build the semantic mask

Create `02_semantic_mask.png` and `02_bg_removed.png` while preserving the source RGB.

1. Use only `isnet-anime` and `isnet-general-use`: use the anime model by default and the general model for an explicitly general subject or automatic enclosed-background adjudication. Do not load BiRefNet or PyTorch.
2. Run only one IS-Net session at a time in a subprocess using ONNX Runtime `CPUExecutionProvider`. Do not register CoreML, MPS, GPU, or ANE providers. Use six OMP threads, a 300-second timeout, and the configured 8 GiB default hard RSS limit.
3. For a fully opaque source, sample the background color from the source border. Exterior-connected matching background is always background; enclosed matching components require semantic confidence.
4. For a binary transparent source, never sample hidden RGB under transparent pixels and never run RGB color-key cleanup. Already-transparent pixels are immutable. `auto` conservatively audits only originally opaque internal cells; both IS-Net models must agree before a cell becomes a repair candidate, and a one-logical-cell boundary guard protects the original silhouette. Model disagreement is ambiguous and blocks export.
5. `preserve` keeps useful binary source Alpha exactly and skips both models. `repair` requires useful binary source Alpha. A user-supplied binary mask has highest precedence, is copied exactly, and skips model inference without changing source RGB.

Keep the model probability in alpha through Pixel Fine. Do not alpha-matte or soften source RGB.

## Explicit white-background fallback after model failure

Semantic `auto` remains the default. Only after an accepted opaque, near-white source has an unusable IS-Net mask, explicitly prepare a **review-only** white candidate. Do not retry export with bare `--background-method white`; the export entry points now require a source-bound main-conversation review. A runtime error without a retained mask is not sufficient evidence. Do not use this route to bypass source acceptance, change the source grid, loosen alpha/color thresholds, or remove white regions by fixed area.

1. Preserve the failed run and its original source/model masks. In a separate folder, write `failure.json` with this schema (mask paths are relative to that JSON):

```json
{
  "schema": "white-fallback-failure/v1",
  "source_sha256": "<SHA-256 of the exact accepted original source>",
  "failure_kind": "semantic_mask_unusable",
  "reason": "<observed missing subject or incorrect mask regions>",
  "source_accepted": true,
  "white_background_suitable": true,
  "model_masks": [
    {"model": "isnet-anime", "path": "failed-mask.png", "sha256": "<mask SHA-256>"}
  ]
}
```

Set the acceptance/suitability fields only after reviewing the source: plain near-white background, readable closed subject outline, no unresolved source defect. Include both allowed model masks if both were run. The tool additionally checks opaque alpha, near-white border at the unchanged threshold 245, evidence hashes, and the original 45–80 source grid.

2. Using the project's Python environment, run `tools/white_fallback.py prepare --source /absolute/accepted-source.png --failure-evidence /absolute/failure.json --output /absolute/new-candidate-directory`. This command copies the source byte-for-byte, preserves the detected grid, produces a candidate plus enlarged preview, and saves **every** surviving background-colored region in `white_regions.json` / `white_regions_review.png` and the contour in `outline_review.png`. It does not invoke Lumina or produce the accepted Stage 3 filenames.
3. The **main-conversation assistant** must inspect the source, `candidate.png`, `candidate_8x.png`, both review images, and every numbered white region. Check outline, white clothing, eye whites, natural eye structure/gaze, and enclosed background holes. Candidate alpha=255 is a color/topology result, not semantic confidence; zero ambiguous semantic components is not approval. A suspected hole, uncertain white region, or broken outline blocks this candidate. Do not auto-fill or auto-delete holes. Preserve the rejected candidate; obtain a separately reviewed corrected binary mask or a new source through the existing authorized routes.
4. Only after that visual review passes, copy `review.template.json` to `review.json` in the same candidate directory. Keep the manifest hash, set `decision` to `approved`, set each named check to `true`, record meaningful review notes, and set **each** numbered component to `{"decision":"foreground","reason":"<what this region depicts>"}`. Missing, unresolved, or background-hole decisions block promotion. Do not invent a main-conversation review or reuse it for a changed source/candidate.
5. Run `tools/white_fallback.py promote --review /absolute/candidate-directory/review.json`. It verifies hashes and the complete review before writing `04_pixel_perfect.png`, `05_pixel_preview_8x.png`, and `approval.json`. Preserve the whole candidate directory. Only now proceed through the usual Stage 4 rules. When using the deterministic pipeline or WorkBuddy `convert`, pass **both** `--background-method white --white-fallback-review /absolute/candidate-directory/review.json`; use the exact reviewed source and a separate export run. Those entry points verify the review before work and compare the resulting refined pixels to the reviewed candidate before Lumina. Do not change padding, square output, alpha policy or mask override in that export.

## Run Pixel Fine on the source grid

Create `03_working_grid.png`, `04_pixel_perfect.png`, and `05_pixel_preview_8x.png`.

- Auto-detect the untouched source grid before semantic masking and require `45–80` cells per axis there only.
- Run Pixel Fine again with semantic confidence in alpha and require the detected grid to match the source preflight exactly.
- Preserve the rectangular grid and never force a fixed fallback grid.
- Add two complete transparent logical rows and columns on every side as temporary working padding. The configured value may change explicitly, but percentage padding is not used by the pipeline.
- For fully opaque sources, resolve background-colored logical components with foreground confidence `>= 0.80` and background confidence `<= 0.20`. In automatic mode, let the general model adjudicate every enclosed background-colored component that the anime model did not confidently reject; this includes high-confidence color/semantic conflicts such as a white gap called foreground by the anime model. A component whose adjudicating samples all remain below `0.50` is background; a component whose median is at least `0.80` is semantic foreground. Treat the unresolved interval as ambiguous.
- For binary transparent sources, remove only originally opaque internal cells for which both models report background confidence `<= 0.20`. Never add foreground into original transparency. Protect every originally opaque logical cell touching original transparency from automatic deletion. Do not run isolated-cell deletion on `preserve`, `repair`, or mask-override routes.
- If the two-model route leaves an ambiguous component, save `02_mask_review_overlay.png` and `02_mask_components.json` and stop before Lumina. Continue only with a corrected source or an approved binary mask; acknowledgement alone does not bypass the ambiguity gate.
- Convert final alpha to exactly `0` or `255`. Isolated one-cell cleanup applies only to the fully opaque semantic route. Preserve semantic foreground whites such as eyes, hair, clothing, and highlights.

## Produce the export grid

- Tight-crop complete transparent rows and columns after cleanup. Preserve internal transparent holes.
- Remove all temporary working padding before physical-size calculation.
- Apply optional square padding only when explicitly requested; it is an intentional export-size change.
- Treat the tight `04_pixel_perfect.png` dimensions as `export_grid`, the only downstream sizing source.
- Enlarge the preview with nearest-neighbor sampling only.

Minor source blur, antialiasing, gradients, and near-identical colors pass when the final grid is stable, readable, binary-alpha, and free of ambiguous background components.

The main-conversation assistant must inspect `04_pixel_perfect.png` and `05_pixel_preview_8x.png` before final acceptance. Judge the whole face for natural eye structure and coherent gaze. Allow differences caused by perspective, slight tilt, and natural partial occlusion; do not impose shared pixel rows, equal iris/pupil row counts, or numerical near/far-eye limits. If a generated result still has obvious misalignment, broken eye shapes, or unexplained distortions, reject it and return to a fresh Stage 1 generation. Preserve a user-provided source unless a creative edit is authorized.

Do not read Lumina settings until the export artifact and preview pass this final gate.
