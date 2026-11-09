# Character covers

## Visual construction

Use a 3:4 portrait canvas (1080×1440). Keep a broad view of the original character artwork retained during generation/research: default to proportional `contain` at zoom 1.0, preserving the complete selected reference region. Gaussian-blur by about 1.6% of canvas width, use background brightness 0.86 and saturation 0.88, and retain its original color relationships. This is a modest lift from the previous 0.78 brightness; do not brighten by adding a white veil or washing out colors. Softly fill any margins with a more blurred version of the same reference; the canvas stays full without stretching or hard letterbox edges. Avoid a tightly cropped giant face or flat color fields. Center a clear, tightly cropped bead silhouette at about 60% of canvas width and up to 52% of height, leaving more original art visible around it. Use equal integer pixels per bead, subtle fused-square surface relief and a soft shadow. Keep the entire subject visible. Place the reviewed Chinese character name below the subject in warm, softly shaded calligraphic lettering, with a clear gap and no overlap. Add a subtle diffuse rim light outside the silhouette, as in the supplied cover reference; keep pixel steps sharp, avoid a thick white outline, and exclude internal holes from the glow. No slogan, signature or watermark; adjust placement by visual review.

The background is the **original illustration/official large reference used for the character**, never our pixel source, mapped preview or bead chart. Inspect it before use and verify the same character and costume against the subject brief/research. On a sheet with several characters, explicitly crop to the matching character, keeping as much head, torso and nearby scene as the source allows while excluding other characters and prominent lettering. Do not crop to only the face and then enlarge it again to fill the portrait. Crop coordinates refer to the EXIF-oriented original. Keep the original file unchanged. Record its source URL/research path and the identity/costume check. Do not fetch a different costume simply because it is easier to fill the canvas. If the retained reference is missing, first recover it from that run's recorded source; if unavailable, report the missing input.

The foreground comes only from the chosen saved `图纸数据.json`. Default to the uncompressed original orientation. Use the compressed variant only when it is the accepted version being shown. Never OCR a chart, recolor the cells, fill transparent holes, connect detached pieces, mirror the character or ask an image model to redraw it for a cover. The deterministic compositor is a project tool; it writes presentation images without touching the chart inputs.

## Existing workflow

Resolve `PYTHON` and `TOOLS_DIR` via [runtime.md](runtime.md). After chart export/review:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" cover /absolute/run \
  --reference /absolute/original_character_reference.jpg \
  --reference-note '已核对：与本次角色及默认服装一致，复用生图时官方原画' \
  --reference-source 'https://official.example/retained-source.jpg'
```

This creates `run/covers/cover/封面.png`, internal `前景.png` and `背景.png`, and `cover.json`. The character name defaults to the saved project title; use `--name-text` for a verified short name if the historical title includes extra outfit/metadata wording. The workflow manifest, source JSON, palette, previews, counts and every file in `delivery/` remain unchanged. `expected_primary_products` stays two/four. The cover is an additional presentation image outside `delivery/`.

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
- `--background-fit contain`: default keeps the full selected reference region, with soft same-art fill at margins. `cover` is an optional closer crop; both use uniform scaling.
- `--focal X Y`: background alignment within the canvas, each 0–1 (default 0.5 0.5).
- `--zoom 1.0`, `--blur 0.016`: background scale relative to the selected fit and Gaussian radius / cover width. Zoom 0.5–1.0 shows the art smaller; values above 1 may crop it. To loosen a close background, first use contain and lower zoom, then broaden the character-isolation crop if appropriate.
- `--brightness 0.86`, `--saturation 0.88`: background-only tone adjustments; lift brightness gently while retaining color and subject contrast.
- `--subject-width 0.60`, `--subject-height 0.52`, `--center 0.5 0.49`: subject containment and placement, leaving more background visible; equal integer cell scale, no stretching.
- `--size 1080 1440`: output dimensions; at most 12 megapixels and 4096 per side.
- `--flat`: flat palette blocks instead of the default subtle bead relief.
- `--name-text '中文角色名'`: reviewed character name; defaults to saved project title. Never translate or invent a name. `--no-name` explicitly restores text-free covers.
- `--name-size 0.078`: font size / canvas width, automatically reduced for a long name; clipping and unsupported glyphs fail before publishing outputs.
- `--name-font /absolute/licensed.ttf`: optional TrueType font override. Verify its license separately; the bundled font's license does not cover another font.
- `--glow 0.40`: subtle diffuse light outside the character silhouette. Use `--glow 0` to disable it; it never changes the saved foreground or chart cells.

## Name style and font license

The default style uses a readable handwritten Chinese face, gentle letter spacing, warm ivory-to-champagne ink, a fine dark edge and a soft shadow. It belongs below the pixel character, with no overlap or white title panel. Prefer the user's familiar Chinese character name; use `--name-text` when the project title includes a full surname, date or costume label that would make an awkward cover name. Long names shrink within the safe width; a missing glyph or impossible fit is a visible error, never a silent system-font substitution.

The unmodified `assets/fonts/LXGWWenKaiLite-Regular.ttf` is bundled with the upstream `OFL.txt` and `source.json` (source URL, pinned revision and SHA-256). Upstream: [LXGW WenKai Lite](https://github.com/lxgw/LxgwWenKai-Lite), under SIL Open Font License 1.1. Keep the full license/copyright notice with redistributed skill/tool bundles and retain the source record; do not sell the font on its own or misrepresent authorship. Custom fonts remain the operator's responsibility to license. The rendered image need not print the font credits. Runtime records the actual font hash, license provenance, text, size, spacing and bounding box in `cover.json`.

The renderer requires saved cells and an explicit reference. Name lettering uses the bundled TrueType font; no system font, network, other skill, image generation, segmentation or Lumina is required. A minimum original long side of 512 rejects tiny logical grids, but does **not** verify identity or prove the file is original art. Visual and provenance checks remain mandatory.

## Acceptance and delivery

Inspect the unblurred reference/crop, full cover and a face/detail view. Verify matching identity/costume, full crisp foreground, correct orientation, visible eyes/outlines, preserved white beads/internal holes/detached pieces, readable bead texture and a background that stays subordinate while retaining recognizable character/scene structure. Check top/bottom and side transitions for visible rectangular edges; avoid featureless oversized face fragments. Review the character name for spelling, font coverage, legibility, balanced spacing and separation from the subject. Keep rim light subtle, outside bead pixels and internal holes. Avoid prominent source lettering in the background crop. Adjust background framing/blur before changing the subject scale. A small-cell pattern may need gentler relief or `--flat`.

`cover.json` records exact input/output hashes, layout, reference source/check and counts derived from cells; `background_framing` additionally records the uniform scale, visible source region/fraction and canvas placement. Its initial status is `cover_ready_for_review`. After visual acceptance, record concise checks there and set its status to `accepted`. Retain the layers internally; show and link only `封面.png` as the extra cover image alongside the required chart files. For a cover-only task, deliver the cover without duplicating the old chart files. When validating an implementation, compare input hashes and chart delivery hashes before/after, not only counts. For a background-only revision, also compare foreground PNG hashes. When changing the subject's display scale, compare the logical cell-center RGBA values at each integer scale instead of expecting identical foreground PNGs. Keep the previous cover for side-by-side review.
