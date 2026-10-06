# Lumina raster color replacement scope fix (draft)

A source color that matches white in the LUT must not replace every white pixel. This patch keeps explicit boolean masks authoritative, otherwise matches `quantized` / `quantized_hex` / `source` against the original quantized raster. A missing source raster fails closed; a source color with no hits changes nothing. Records containing only `matched` / `matched_hex`, and legacy dictionary mappings, retain global matched-color behavior.

The GUI no longer unions source-color hits with unrelated matched-color hits. Fresh preview caches retain the LUT Lab coordinates and layer stacks, so the existing preview replacement callback updates RGB and material matrices together and undo restores both. Old preview caches retain their previous display-only behavior until refreshed. The existing formal raster export uses the same scope resolver and application helper. Vector normalization and REST request schemas are unchanged; this patch adds no endpoint, UI, global LUT, or default matching changes.

The externally cloned Lumina software is intentionally excluded from this repository. The reviewable patch includes its regression tests and targets upstream commit `8af9cdfd513fcde3d98c3e4de7bb36620942f51a`. It has been exercised in an isolated worktree; it is **not automatically installed** or merged.

Apply to a clean isolated Lumina checkout for review:

```bash
git -C Lumina-Layers rev-parse HEAD
git -C Lumina-Layers apply --check ../patches/lumina-source-color-scope.patch
git -C Lumina-Layers apply ../patches/lumina-source-color-scope.patch
cd Lumina-Layers
../.venv/bin/python -m pytest tests/test_source_color_scope_regression.py tests/test_palette_connected_selection_unit.py tests/test_color_replace_unit.py tests/test_converter_generate_unit.py tests/test_user_replacement_list_ui_unit.py -k 'not full_pipeline_replacement_regions_affect_preview_and_model' -q
```

Validation: **49 focused/existing tests passed**, plus the previously deselected full-pipeline test **passed in 312.95 seconds**. The original test and algorithm parameters were unchanged; OpenCV was set to one thread for this run. Both sample-logo models were generated. No requested check remains skipped. One existing Gradio label warning remains. `git diff --check` and clean-upstream patch application checks passed. No Hsin geometry or 3MF was generated.

Run the full-pipeline test independently with the same parameters and bounded OpenCV threading:

```bash
../.venv/bin/python -c 'import cv2, pytest; cv2.setNumThreads(1); raise SystemExit(pytest.main(["tests/test_user_replacement_list_ui_unit.py::test_process_batch_generation_full_pipeline_replacement_regions_affect_preview_and_model", "-q", "-s"]))'
```

The new regression fixture has 1,466 white matched cells but only seven cells of the selected source color; source selection changes exactly seven RGB/material cells, explicit masks remain bounded, and protected white cells stay unchanged. Additional cases cover empty masks, source no-hit, missing quantized raster, malformed masks, transparency, overlapping records, legacy matched-only behavior, GUI source/output color collisions and preview undo.

Actual Hsin diagnostic evidence is separately stored in private `Aurxs/pixelartspace`, under `artifacts/2026-10-06/hsin/manual_hair_gray/scoped_candidates/`. At hue 0.6 the two real LUT entries (13 and 3) each changed only the parent-approved diagnostic mask's 240 logical cells, with zero RGB/material changes outside it. The preview arrays equal the real `convert_image_to_3d` entry's raster outputs, captured immediately after replacements and stopped before geometry. The actual seven-cell source case also passes. Diagnostic scope approval is not final visual adoption; no delivery files were overwritten.

## Parent-review follow-up

Both GUI selection routes store source RGB in `conv_selected_color`: the image-click wrapper uses `_resolve_click_selection_hexes(...)[1]`, and the palette-trigger wrapper also returns that source state while displaying the matched color. The apply callback receives this state. A cached source selection now rejects a different selected RGB, including an accidentally supplied matched color, before reusing any cached region. Regression tests cover the state/display split and stale region rejection.

Arbitrary non-LUT replacement RGB retains historical behavior: the display uses the requested RGB and the material stack uses its nearest calibrated LUT entry. This patch does not redefine that unrelated behavior. The diagnostic entries 13 and 3 use exact calibrated RGB values; their RGB and layer stacks were verified against the LUT. An additional regression test documents the non-LUT behavior explicitly.

The user subsequently rejected broad 240/235-cell gray treatment. Those diagnostic artifacts are retained only for comparison; further artwork work is limited to a new, separately reviewed, very small hair-boundary coordinate proposal. This does not change the code regression result.
