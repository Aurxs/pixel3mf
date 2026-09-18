# Charts and delivery

## Standard four-chart workflow

Resolve `PYTHON` and `TOOLS_DIR` using [runtime.md](runtime.md). After the original logical grid passes review, start a new run:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" prepare \
  /absolute/original_logical.png /absolute/new_run --title '作品名' --target 52
```

This retains the original, renders an uncompressed mirror pair, and prepares a size-constrained AI draft. Read `manifest.json` for the absolute `ai_input` and `ai_prompt` paths. Inspect the input, call the host image tool once using the generated prompt and that exact input, then finish:

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
    02_compression/                 seed, prompt, AI original, checks and refined grid
    03_compressed_attempt-1/        pair + preview/PDF/CSV/JSON
  delivery/
    01_未压缩.png
    02_未压缩_镜像.png
    03_压缩.png
    04_压缩_镜像.png
```

Only these four PNGs are primary deliverables. Do not place comparisons, PDFs, ZIPs or material lists in `delivery/`. The uncompressed pair trims all empty outer rows and columns from its cell matrix before rendering. Both the actual chart grid and reported dimensions use the occupied bounding box, with no outer blank rows or columns. Occupied cells and internal holes remain unchanged; no resampling occurs and palette matching still applies. The fitted pair is centered on the requested board and uses the same mapping settings, with the selected palette fixed during AI refinement. Do not rerender the uncompressed pair from the compressed or AI-modified image.

`prepare` accepts `--max-colors`, `--palette`, `--outline auto|black|none` and `--font`. Color limits are opt-in. Palette and font paths should be absolute. Exact count and mirror invariants are retained independently for each size. Keep the main chart title as the work name, adding only “镜像版” for mirrors; dimensions in the statistics and the filenames distinguish sizes.

## Lower-level renderer

Use the project tool paths and a compatible interpreter. The source must be a logical grid (one actual pixel = one bead), not its enlarged preview. Default maximum grid is 256 cells per axis.

```bash
"$PYTHON" "$TOOLS_DIR/bead_pattern.py" \
  /absolute/04_pixel_perfect.png /absolute/run/charts \
  --title '我的拼豆作品'
```

Optional controls:

- `--max-colors 15`: at most 15 actual colors, not a mandatory count. Defaults to no cap.
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

Inspect the four primary charts, including one detail crop for each size. Verify asymmetrical features change sides, text remains readable, per-color sum equals occupied cells, and blanks are not counted. Inspect PDF rendering if the optional PDF will be delivered. Report multiple orthogonally disconnected components as a construction consideration; do not join them automatically. Only examine relevant outputs and run the focused repository bead tests when changing code.
