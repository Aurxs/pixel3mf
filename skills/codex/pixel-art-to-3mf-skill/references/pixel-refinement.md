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


### Explicit correction of visually confirmed background regions

When the main-conversation assistant has classified specific numbered regions as background, use `tools/white_fallback.py correct --candidate /absolute/original-candidate-directory --decisions /absolute/correction-decisions.json --output /absolute/new-directory`. This is a review-only correction, not approval. Do not use the unrelated hardcoded `remove_selected_white_holes.py` script.

The decisions JSON must use schema `white-fallback-correction/v1`, `reviewer_role: "main-conversation"`, `manifest_sha256` for the original `candidate.json`, and `candidate_sha256` for its `candidate.png`. Its `components` object must name **every original component ID**, with `decision: "background"` only for explicitly confirmed holes, otherwise `decision: "preserve"`, and a meaningful `reason` for each. A preserve instruction means no edit, not final foreground acceptance. IDs refer to `white_regions.json`, not labels used in other diagnostic images. There is no wildcard, threshold override or all-white deletion option; a nonempty proper subset must be selected.

The tool verifies artifact hashes and reconstructs each original component membership at the unchanged tolerance. It clears only the selected logical cells' Alpha, preserving all RGB (including hidden RGB), every other Alpha, source bytes, and source/working grid dimensions. It then tight-crops only completely transparent outer rows and columns; a fully transparent result is rejected. This does not resample pixels or reapply the source density gate. It retains the parent evidence and writes a separate `candidate.png`, nearest-neighbor preview, logical-resolution `candidate_mask.png`, magenta `correction_diff_8x.png`, `correction.json`, updated region/outline reviews and a new pending review template. Source-resolution cutouts and semantic diagnostics copied into the new directory are retained **parent evidence**, not the corrected mask. No prior review or approval is copied or reused; no automatic hole cleanup or conversion runs. Keep the original rejected candidate.

`correction.json` records the parent and new candidate grids, the crop box in parent-candidate coordinates (right/bottom exclusive), and both origins in the unchanged working grid. `removed_candidate_xy` and the full-size difference preview remain in the **parent candidate** frame, so all authorized deletions remain inspectable even when their rows are cropped away. Remaining white-region IDs and bounding boxes stay in working-grid coordinates. Use the new candidate origin when mapping final pixels back to the original sampling boundaries; never reuse old candidate coordinates without this translation.

The main-conversation assistant must review the corrected image, mask, changes, remaining whites, outline and gaze before filling the new `review.json` and promoting it. The unchanged white export pipeline re-creates the original color/topology result and must still reject a corrected candidate mismatch; do not disable that equality guard or relabel the source to bypass it. This correction command supplies a separately reviewable logical binary mask and final grid, not a new automatic conversion route. Follow Stage 4 only after the new visual acceptance.

## Run Pixel Fine on the source grid

Create `03_working_grid.png`, `04_pixel_perfect.png`, and `05_pixel_preview_8x.png`.

- Auto-detect the untouched source grid before semantic masking and require `45–80` cells per axis there only.
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

The main-conversation assistant must inspect `04_pixel_perfect.png` and `05_pixel_preview_8x.png` before final acceptance. Judge the whole face for natural eye structure and coherent gaze. Allow differences caused by perspective, slight tilt, and natural partial occlusion; do not impose shared pixel rows, equal iris/pupil row counts, or numerical near/far-eye limits. If a generated result still has obvious misalignment, broken eye shapes, or unexplained distortions, reject it and return to a fresh Stage 1 generation. Preserve a user-provided source unless a creative edit is authorized.

Do not read Lumina settings until the export artifact and preview pass this final gate.

## Reviewed correction plus one-cell bridge handoff

For an existing formal white-region correction followed by exactly one source-supported
bridge from `tools/beads/bridge_pixels.py`, use the controlled
`tools/reviewed_bridge_export.py` entrypoint. Do not replace the corrected/bridged
pixels by rerunning the original white export, relabel the final grid as the original
source, or call the low-level converter before promotion.

1. Run `prepare --original <original-white-candidate-dir> --corrected <formal-correction-dir>
   --project <bridge-input.json> --evidence <sampling-evidence.json>
   --result <formal-bridge-result.json> --candidate <final.png> --output <new-review-dir>`.
   It snapshots the complete evidence, replays original source-density and white
   preparation checks (using retained masks, without model inference), replays the
   formal correction, checks the exact source sampling boundaries and lossless
   palette, and reruns the formal bridge entrypoint with budget one. The final
   RGBA must equal the corrected candidate plus that unique reported cell. It
   creates only a pending review bundle; no pixels are resampled for export.
2. The main-conversation assistant must inspect the final candidate, enlarged
   preview, correction and bridge changes, and all remaining numbered whites.
   Copy `review.template.json` to `review.json`, retaining its new schema
   `reviewed-bridge-review/v1`, `manifest_sha256` and `candidate_sha256`. Record the
   actual main approval, all checks (including `correction_and_bridge_reviewed`),
   and a meaningful foreground reason for each surviving white-region ID.
   Earlier white-candidate reviews and approvals cannot authorize this new bundle.
   A main approval already given for the exact final PNG may be transcribed only
   after the new bundle has been verified to bind that same PNG and reviewed chain.
3. Run `tools/reviewed_bridge_export.py promote --review <review.json>`.
   It revalidates all hashes, the source/correction/bridge replay, the exact final
   candidate and nearest-neighbor preview, and the fresh main review. Only then
   does it copy the exact PNG bytes to `04_pixel_perfect.png` and the preview to
   `05_pixel_preview_8x.png`, recording `approval.json`. Existing promotions are
   never overwritten. Continue to Stage 4 through this entrypoint's `convert`.

This route is limited to a formal original white candidate, one formal region
correction, and exactly one formal source-supported bridge. Other edits remain
unsupported. The original pipeline's reconstruction/equality guard is unchanged.
