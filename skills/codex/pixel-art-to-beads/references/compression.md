# Board-size compression workflow

Resolve `PYTHON` and the project’s `TOOLS_DIR` using [runtime.md](runtime.md).

This is the fitted branch of the default four-chart workflow; the parallel uncompressed branch trims transparent outer padding without resizing any bead cells. Default single-board target is 52×52 for this user; explicit targets take precedence. Already-small artwork is centered without enlargement.

The selected standard workflow is **algorithmic sizing, then AI refinement, then automatic Perfect Pixel validation**. Requests to improve the compression prompt refer to the generated prompt in this workflow. Direct AI downsizing experiments are not part of the installed workflow.

## 1. Always restart from the original accepted logical grid

The input is the untouched final pixel source with binary alpha, before previous compression/AI passes. Record its hash. Do not feed a patched or rejected AI candidate back as the new source. Raw or enlarged artwork first goes through normal preparation.

```bash
"$PYTHON" "$TOOLS_DIR/compress_pixels.py" prepare \
  /absolute/original_logical.png /absolute/new_run \
  --target 52 --outline auto
```

Optional `--max-colors N` and `--palette` control palette mapping. No hardcoded 15-color cap is applied. `--outline auto` protects a black exterior when at least 90% of the source's exterior edge is dark. `--outline black` explicitly requires black-outline protection; `--outline none` preserves unoutlined art. Custom palettes can provide a near-black `--outline-code` instead of MARD H7.

The deterministic stage trims only transparent outer space, scales proportionally by area-weighted color-code voting, and centers the result on the target canvas. Occupancy coverage and color votes are computed separately. It does not enlarge already-small artwork. For protected outlines, it locks one occupied-cell-wide exterior shell to the black code, without enlarging the silhouette or painting over internal eye/face regions. Enclosed cutout holes remain empty.

Palette selection is independent of outline protection. Enabling black-outline preservation must not reselect all colors or change interior eye/mouth cells in the algorithmic draft. Select the palette once, then apply black only to the exterior shell. If the outline would exceed an explicit color cap, report that conflict instead of silently selecting a different palette. Tied area votes favor the original center cell.

Outputs: original copy, `01_seed.png`, enlarged solid-color-background `02_ai_input.png`, fully rendered generic `03_prompt.txt`, and `run.json`. Background color is selected to be distinct from used subject colors; it is never assumed to be white. Do not substitute a new character-specific prompt or coordinate patch.

For algorithm-only requests, inspect `01_seed.png` and export `run.json` with the chart tool. For AI assistance, continue below. Be accurate about the division of work: the algorithm establishes the smaller grid; AI rearranges small internal pixel clusters.

## 2. One bounded AI pass using the generated compression prompt

Inspect and attach `02_ai_input.png` as the edit target to the host's built-in image tool. Send the complete `03_prompt.txt`. This keeps the prompt reusable: target size, outline treatment and reserved background color come from run metadata; it contains no hardcoded subject or image coordinates.

The prompt preserves the target grid, silhouette, expression, key color regions, eye whites and opaque clothing whites. Black outer-edge cells are explicitly locked; the model must not replace them with hair or skin colors. Allow small whole-cell readability edits inside the silhouette, not a redesign or extra detail.

For faces, preserve separate eyelid/pupil, iris-color and eye-white cells, gaze and perspective. Preserve the mouth's open/closed expression and stepped shape; avoid merging it with skin or turning it into a rectangular stamp or dot. Sacrifice secondary hair shading before facial readability. These are general instructions, not character-specific coordinates. A correct grid and intact outline alone do not constitute a visual pass.

Use an ordinary opaque, uniform reserved-color background for this compression route. Its removal after sampling creates actual RGBA transparency. Do not claim that a text `background="transparent"` string is a tool parameter or evidence of a transparent file. Never ask the model to render a transparency-preview pattern.

## 3. Automatic refinement and invariant checks

```bash
"$PYTHON" "$TOOLS_DIR/compress_pixels.py" finish \
  /absolute/new_run /absolute/generated.png --attempt attempt-1
```

Perfect Pixel detects the grid automatically, with no forced grid or fallback resize. A different size rejects the candidate. The reserved background must match at least 95% of known empty cells, or the candidate is rejected; real alpha is also accepted. Major silhouette changes are rejected. Small sampling discrepancies (at most 1% of occupied cells, minimum four cells) are restored to the known seed mask; missing foreground cells use the seed's color.

The final palette remains the seed's actual palette. All locked exterior cells are restored to the outline code automatically after AI and mapping. This is a reproducible constraint, not manual retouching. Every restored cell count is recorded. No per-character exceptions, hand-selected holes or coordinates are permitted in this workflow.

Outputs per attempt: untouched AI output, sampled grid, `02_final.png`, enlarged preview, `project.json`, and a report with measured size, background mode, mask corrections and outline corrections.

At most two AI calls per run. A retry uses the same original-derived draft and adjusts only the violated generic instruction. At the limit, retain the failure report and present the valid algorithm draft separately; do not silently hand-fix an AI result into a pass. A numeric pass still needs one visual review for facial readability and style.

## 4. Export once the generic workflow passes

```bash
"$PYTHON" "$TOOLS_DIR/bead_pattern.py" \
  /absolute/new_run/attempt-1/project.json /absolute/new_run/charts --title '作品名'
```

For standard four-chart delivery, prefer `run_workflow.py finish` from [bead-export.md](bead-export.md), which runs refinement and publishes this pair alongside the uncompressed pair. The lower-level commands above are for focused debugging or explicit single-pair requests. A representative original-source end-to-end run validates workflow changes; do not repeatedly polish one image as a substitute for improving the workflow. Repository tests cover scaling bounds, transparency and exterior-only outline preservation.
