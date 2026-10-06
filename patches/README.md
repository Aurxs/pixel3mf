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

Validation: **45 passed, 1 deselected**, one existing Gradio label warning. The deselected upstream test generates full geometry for an unrelated sample logo; its initial run was stopped during that expensive full-model test's image-processing stage. All replacement, GUI selection, API generation routing, preview material, undo and legacy-scope checks above passed. `git diff --check` passed. No Hsin geometry or 3MF was generated.

The new regression fixture has 1,466 white matched cells but only seven cells of the selected source color; source selection changes exactly seven RGB/material cells, explicit masks remain bounded, and protected white cells stay unchanged. Additional cases cover empty masks, source no-hit, missing quantized raster, malformed masks, transparency, overlapping records, legacy matched-only behavior, GUI source/output color collisions and preview undo.

Actual Hsin diagnostic evidence is separately stored in private `Aurxs/pixelartspace`, under `artifacts/2026-10-06/hsin/manual_hair_gray/scoped_candidates/`. At hue 0.6 the two real LUT entries (13 and 3) each changed only the parent-approved diagnostic mask's 240 logical cells, with zero RGB/material changes outside it. The preview arrays equal the real `convert_image_to_3d` entry's raster outputs, captured immediately after replacements and stopped before geometry. The actual seven-cell source case also passes. Diagnostic scope approval is not final visual adoption; no delivery files were overwritten.
