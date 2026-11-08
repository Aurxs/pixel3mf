# Character covers

## Visual construction

Use a 3:4 portrait canvas (1080×1440). Fill it with the original character artwork retained during generation/research, enlarge around the character, Gaussian-blur by about 2.6% of canvas width, and modestly dim/desaturate it. Center a clear, tightly cropped bead silhouette at about 70% of canvas width and up to 62% of height. Use equal integer pixels per bead, subtle fused-square surface relief and a soft shadow. Keep the entire subject visible. No title, caption, signature, watermark or reserved text panel; adjust placement by visual review.

The background is the **original illustration/official large reference used for the character**, never our pixel source, mapped preview or bead chart. Inspect it before use and verify the same character and costume against the subject brief/research. On a sheet with several characters, explicitly crop to the matching character. Crop coordinates refer to the EXIF-oriented original. Keep the original file unchanged. Record its source URL/research path and the identity/costume check. Do not fetch a different costume simply because it is easier to fill the canvas. If the retained reference is missing, first recover it from that run's recorded source; if unavailable, report the missing input.

The foreground comes only from the chosen saved `图纸数据.json`. Default to the uncompressed original orientation. Use the compressed variant only when it is the accepted version being shown. Never OCR a chart, recolor the cells, fill transparent holes, connect detached pieces, mirror the character or ask an image model to redraw it for a cover. The deterministic compositor is a project tool; it writes presentation images without touching the chart inputs.

## Existing workflow

Resolve `PYTHON` and `TOOLS_DIR` via [runtime.md](runtime.md). After chart export/review:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" cover /absolute/run \
  --reference /absolute/original_character_reference.jpg \
  --reference-note '已核对：与本次角色及默认服装一致，复用生图时官方原画' \
  --reference-source 'https://official.example/retained-source.jpg'
```

This creates `run/covers/cover/封面.png`, internal `前景.png` and `背景.png`, and `cover.json`. The workflow manifest, source JSON, palette, previews, counts and every file in `delivery/` remain unchanged. `expected_primary_products` stays two/four. The cover is an additional presentation image outside `delivery/`.

Use `--variant compressed` only if that exported variant exists and has passed visual review. Use `--name cover-2` for a new attempt; existing output directories are never overwritten. A cover attempt does not accept the charts automatically.

## Saved chart outside a workflow

For historical chart projects, use the same compositor directly; do not regenerate their charts:

```bash
"$PYTHON" "$TOOLS_DIR/render_cover.py" \
  /absolute/图纸数据.json /absolute/new_cover_directory \
  --reference /absolute/original_character_reference.jpg \
  --reference-note '已核对角色和服装，与该图纸对应的生图原画一致' \
  --reference-source /absolute/00_official_character_research.md
```

Useful controls (all optional):

- `--reference-crop LEFT TOP RIGHT BOTTOM`: isolate one character in a multi-character original.
- `--focal X Y`: background crop alignment, each 0–1 (default 0.5 0.5).
- `--zoom 1.12`, `--blur 0.026`: background enlargement and Gaussian radius / cover width.
- `--brightness 0.78`, `--saturation 0.88`: background-only tone adjustments.
- `--subject-width 0.70`, `--subject-height 0.62`, `--center 0.5 0.49`: subject containment and placement; equal integer cell scale, no stretching.
- `--size 1080 1440`: output dimensions; at most 12 megapixels and 4096 per side.
- `--flat`: flat palette blocks instead of the default subtle bead relief.

The renderer requires saved cells and an explicit reference; it does not use another skill, network, image generation, segmentation, font or Lumina. A minimum original long side of 512 rejects tiny logical grids, but does **not** verify identity or prove the file is original art. Visual and provenance checks remain mandatory.

## Acceptance and delivery

Inspect the unblurred reference/crop, full cover and a face/detail view. Verify matching identity/costume, full crisp foreground, correct orientation, visible eyes/outlines, preserved white beads/internal holes/detached pieces, readable bead texture and a background that stays subordinate. No text should be added by the compositor; avoid prominent source lettering in the background crop. Adjust background settings before changing the subject scale. A small-cell pattern may need gentler relief or `--flat`.

`cover.json` records exact input/output hashes, layout, reference source/check and counts derived from cells; its initial status is `cover_ready_for_review`. After visual acceptance, record concise checks there and set its status to `accepted`. Retain the layers internally; show and link only `封面.png` as the extra cover image alongside the required chart files. For a cover-only task, deliver the cover without duplicating the old chart files. When validating an implementation, compare input hashes and chart delivery hashes before/after, not only counts.
