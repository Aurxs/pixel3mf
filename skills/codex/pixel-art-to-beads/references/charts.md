# Charts and delivery

Use an absolute skill path and a compatible interpreter. The source must be a logical grid (one actual pixel = one bead), not its enlarged preview. Default maximum grid is 256 cells per axis.

```bash
"$PYTHON" "$SKILL_DIR/scripts/bead_pattern.py" \
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
"$PYTHON" "$SKILL_DIR/scripts/bead_pattern.py" \
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

Inspect both charts, one detail crop and the rendered PDF overview/detail. Verify asymmetrical features change sides, text remains readable, per-color sum equals occupied cells, and blanks are not counted. Report multiple orthogonally disconnected components as a construction consideration; do not join them automatically. Only examine these relevant outputs and run the bundled focused tests when changing code.
