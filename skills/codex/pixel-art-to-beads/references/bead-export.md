# Charts and delivery

## Standard size-aware workflow

Resolve `PYTHON` and `TOOLS_DIR` using [runtime.md](runtime.md). After the original logical grid passes review, resolve a Chinese-first chart title using the naming policy in [SKILL.md](../SKILL.md#chinese-titles-and-accompanying-copy), then start a new run:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" prepare \
  /absolute/original_logical.png /absolute/new_run --title '中文作品名' --target 52
```

This retains the original and renders an uncompressed mirror pair. Input must be the accepted logical grid, not an enlarged preview. After trimming transparent outer padding, both dimensions <= target (default 52) means **two charts only**; do not pad before deciding. `manifest.json` records `logical_size`, `compression_required` and `expected_primary_products` (2 or 4). For `compression_required: false`, skip compression and AI entirely and run:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" finish /absolute/new_run
```

Only if either logical dimension exceeds the target does prepare create a size-constrained AI draft. Read `manifest.json` for the absolute `ai_input` and `ai_prompt` paths. Inspect the input, call the host image tool once using the generated prompt and that exact input, then finish:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" finish \
  /absolute/new_run --candidate /absolute/generated.png
```

For an explicitly algorithm-only request, use `finish /absolute/new_run --algorithm-only`. On an AI failure, preserve the report and use at most one additional fresh call from the original-derived draft; pass `--attempt attempt-2` to retain both results. Do not call the separate compression `finish` first: the workflow entry point already performs it.

Each run has this structure:

```text
<run>/
  manifest.json
  review.json                       written after visual acceptance
  work/
    00_original.* / 00_source.png
    01_uncompressed/                pair + preview/PDF/CSV/JSON
    02_compression/                 oversized only: seed, prompt, AI original, checks and refined grid
    03_compressed_attempt-1/        oversized only: pair + preview/PDF/CSV/JSON
  delivery/
    01_未压缩.png
    02_未压缩_镜像.png
    03_压缩.png                     oversized only
    04_压缩_镜像.png                oversized only
```

Only the required two or four PNGs are primary deliverables. Small runs report `two_charts_ready_for_review`; oversized runs report `four_charts_ready_for_review`. Both require visual acceptance before setting `accepted`. Do not place comparisons, PDFs, ZIPs or material lists in `delivery/`. The uncompressed pair trims all empty outer rows and columns from its cell matrix before rendering. Both the actual chart grid and reported dimensions use the occupied bounding box, with no outer blank rows or columns. Occupied cells and internal holes remain unchanged; no resampling occurs and palette matching still applies. The fitted pair is centered on the requested board and uses the same mapping settings, with the selected palette fixed during AI refinement. Do not rerender the uncompressed pair from the compressed or AI-modified image.

`prepare` accepts `--max-colors`, `--allowed`, `--locked`, `--palette`, `--outline auto|black|none` and `--font`. Both sizes receive the same mapping constraints. The numeric cap is an explicit candidate setting, not an automatic acceptance rule. Palette and font paths should be absolute. Exact count and mirror invariants are retained independently for each size. Use the Chinese work name as the main chart title, optionally followed by the Japanese name in parentheses, adding only “镜像版” for mirrors; dimensions in the statistics and the filenames distinguish sizes.

## Effect-first color merging

Prefer about 18 MARD colors as a starting target when the user has not specified another goal. Natural appearance and quality take precedence; do not force 18 colors or add unused colors: keep more colors when a smaller palette merges eyes, mouth steps, skin/hair separation or identifying costume regions. An explicit hard inventory limit remains a user constraint; explain a visible tradeoff instead of silently exceeding it.

1. Retain the accepted, uncompressed logical source and an uncapped mapped preview/counts as the baseline. Start every palette trial from that source, never a previously reduced preview or old 52-cell output.
2. Use the existing CIELAB matcher with `--max-colors 18` as a candidate. Review similar shades first. Low bead count is a review hint, not permission to delete a color: a few eye-white, iris, upper/lower lip or accessory cells may carry the expression. Choose `--locked` anchors from the actual palette after inspecting those regions; do not hardcode character-specific codes into the skill.
3. Review structure and color loss separately. First compare the newly compressed drawing with the original for eye shape, gaze and mouth topology; a previous acceptance label does not prove those structures are sound. Then compare before/after palette reduction on the **same structural grid**, side by side at full view and with matching enlarged face crops (eyes and mouth). This isolates new color-merging loss from damage already caused by compression or AI. If a structural defect is found, revise and review that drawing before judging its reduced palette; unchanged silhouette, cell count or bead count alone cannot establish visual quality. The weighted matcher favors large regions and does not understand faces. Locks keep codes available during palette selection; they do not lock cell coordinates or guarantee that AI preserves a mouth. Raise the candidate cap or keep the baseline if visual separation is lost. Record which merges were accepted and which small detail colors were retained.
4. Freeze the approved code list with `--allowed CODE1,CODE2,...` for the size-aware run, and pass the same `--locked` anchors. Both sizes must use this shared codebook; actual usage counts may differ. Include the protected outline code when outline protection is active. Do not select a new palette independently for the 52-cell branch. If a revision is needed, regenerate both sizes from the unchanged source with the revised shared list.

When both the original logical grid and a newly accepted 52-cell result already exist, consider their occupied colors together when choosing the shared list. Reuse the existing frequency-weighted CIELAB selector with reviewed detail anchors; then remap each retained grid separately using the fixed allowed list. This is palette selection only: keep both grids and occupancy masks unchanged. Do not use an old compressed result as a substitute for a newly requested compression, and do not turn example character codes into universal anchors.

5. Inspect both mapped previews and the post-AI result before acceptance. In `review.json`, record separate structure and palette-comparison findings, baseline/candidate/final color counts, shared codes, retained detail anchors and concise visual reasons for any result above the preferred target. Check the union of actually used codes against the reviewed target, unchanged occupancy/grid/bead counts for palette-only remapping, preserved black outline and eye-white cells, and exact mirror relationships. If it fails, try a small anchor adjustment; otherwise report the smallest visually acceptable excess over the target. Report actual color count and bead count separately for each size; no need to print this internal review on the chart.

`--max-colors` is a hard limit inside the algorithm, so use it to propose a candidate, not as a claim that the result looks good. Once the shared list has passed review, `--allowed` alone can fix that codebook without imposing a second, smaller cap. A fixed list constrains available colors; unused codes need not be forced into either image.

## Lower-level renderer

Use the project tool paths and a compatible interpreter. The source must be a logical grid (one actual pixel = one bead), not its enlarged preview. Default maximum grid is 256 cells per axis.

```bash
"$PYTHON" "$TOOLS_DIR/bead_pattern.py" \
  /absolute/04_pixel_perfect.png /absolute/run/charts \
  --title '我的拼豆作品'
```

Optional controls:

- `--max-colors 18`: at most 18 actual colors, not a mandatory count. Defaults to no cap.
- `--palette /absolute/palette.json`: custom JSON or CSV.
- `--allowed H2,H5,H6,H7,E13`: use only this inventory.
- `--locked H2,H7`: keep anchors available during color reduction.
- `--canvas 50x50`: center on a larger transparent canvas, no resizing.
- `--fill H2`: replace all empty cells with this bead code, including internal holes. Use only when a complete filled background is intended. Filling consumes a color slot; if it exceeds the cap, the tool asks for a parameter correction.
- `--major-every 5`: major grid interval.
- `--spare-percent 5`: CSV adds optional procurement quantity; actual counts remain unchanged.
- `--font /absolute/font.ttf`: CJK font override.
- `--peg-pitch-mm 2.6`: only when the actual peg pitch is known. This adds 1:1 tiled pages plus a 50 mm calibration line. A nominal bead diameter is not evidence of peg pitch. Default PDF is a reading chart, not physical-scale placement.

Re-render an existing project (no recoloring):

```bash
"$PYTHON" "$TOOLS_DIR/bead_pattern.py" \
  /absolute/图纸数据.json /absolute/run/reformatted --title '新标题'
```

For a new palette or color cap, return to retained `源像素网格.png`. Do not repeatedly quantize the previously mapped preview.

## Output

- `正常版.png`, `镜像版.png`: upright title, cell codes, four-sided coordinates, major lines, per-color counts.
- `正常版_预览.png`, `镜像版_预览.png`: unlabelled nearest-neighbor mapped previews, transparent empty cells.
- `打印图纸.pdf`: normal and mirror overviews, readable detail pages when needed, shared material list. Tiled pages retain global coordinates with no missing or repeated cells.
- `用量清单.csv`: exact counts and optional spare quantities; UTF-8 BOM for spreadsheet compatibility.
- `图纸数据.json`: canonical cells, palette, provenance, parameters, counts and connected components.
- `源像素网格.png`, `原始输入.*`: retained source for remapping (image-input runs).

Normal and mirror PNGs have identical dimensions and counts. Mirroring flips artwork, including any text that is part of the artwork, but never flips chart labels. Coordinates start at 1 from each variant's own top-left. The material list is for one work; making both physical variants needs twice the listed quantity.

## Review

Inspect the required two or four primary charts, including one detail crop for each size. Verify asymmetrical features change sides, text remains readable, per-color sum equals occupied cells, and blanks are not counted. Inspect PDF rendering if the optional PDF will be delivered. Report multiple orthogonally disconnected components as a construction consideration; do not join them automatically. Only examine relevant outputs and run the focused repository bead tests when changing code.
