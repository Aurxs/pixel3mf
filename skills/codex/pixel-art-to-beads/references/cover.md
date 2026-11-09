# Character covers

## Visual construction

Use a 3:4 portrait canvas (1080×1440). Keep a broad view of the original character artwork retained during generation/research: default to proportional `contain` at zoom 1.0, preserving the complete selected reference region. Gaussian-blur by about 1.6% of canvas width, use background brightness 0.86 and saturation 0.88, and retain its original color relationships. This is a modest lift from the previous 0.78 brightness; do not brighten by adding a white veil or washing out colors. Softly fill any margins with a more blurred version of the same reference; the canvas stays full without stretching or hard letterbox edges. Avoid a tightly cropped giant face or flat color fields. Center a clear, tightly cropped bead silhouette at about 60% of canvas width and up to 52% of height, leaving more original art visible around it. Use equal integer pixels per bead, subtle fused-square surface relief and a soft shadow. Keep the entire subject visible. Place the reviewed Chinese name as `「角色名」` below the subject in plain white PingFang SC Light, with a clear gap and no overlap. Do not add a text gradient, outline or shadow. Add a subtle diffuse rim light outside the silhouette, as in the supplied cover reference; keep pixel steps sharp, avoid a thick white outline, and exclude internal holes from the glow. No slogan, signature or watermark; adjust placement by visual review.

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
- `--name-text '中文角色名'`: reviewed character name; defaults to saved project title. The default style adds `「」` exactly once; already quoted input also works. Never translate or invent a name. `--no-name` explicitly restores text-free covers.
- `--name-style pingfang_light`: default, plain white PingFang SC Light. At 1080×1440 use initial size 40 pixels, tracking 5 pixels and ink center (540, 1138); scale proportionally with the canvas. Text must remain below the subject, with no overlap.
- `--name-size 0.037037037`: optional font size / canvas width (default 40/1080 for PingFang), automatically reduced for a long name. Clipping and unsupported glyphs fail before publishing outputs.
- `--name-font /absolute/existing-font.ttc`: existing authorized TTF/OTF/TTC path. For the default style the file must contain the exact PostScript face `PingFangSC-Light`; the renderer locates its collection index instead of assuming face zero. Without a path, inspect local macOS PingFang locations or fontconfig and verify the actual face. A fontconfig fallback never counts as PingFang.
- `--glow 0.40`: subtle diffuse light outside the character silhouette. Use `--glow 0` to disable it; it never changes the saved foreground or chart cells.

## Name style and font license

The default uses the environment's existing PingFang SC Light (`PingFangSC-Light`) with corner quotes, plain white ink and gentle spacing. Prefer the user's familiar Chinese name; use `--name-text` when the project title includes a full surname, date or costume label that would make an awkward cover name. Long names shrink within the safe width. Font identity, all name glyphs and both quote glyphs must pass checks. Missing font, missing glyphs or an impossible fit are visible errors; do not silently substitute or present an alternative as PingFang. Report the exact font/glyph requirement and keep the named cover pending. Existing charts remain deliverable. Use an authorized Mac's local system font if available; do not copy, extract, upload, download from unofficial mirrors or package Apple font files in the repository or skill. The renderer reads the selected font locally and writes only raster images and provenance.

The earlier warm calligraphic style remains available only through explicit `--name-style warm_calligraphic`, when requested. It uses the unmodified `assets/fonts/LXGWWenKaiLite-Regular.ttf`, bundled with upstream `OFL.txt` and `source.json` (source URL, pinned revision and SHA-256), or an explicitly supplied licensed font. It is not a fallback for missing PingFang. Keep the full SIL OFL 1.1 notice/source record with redistributed WenKai bundles. Custom font permission must be verified separately. Runtime records the actual font hash, family, style, PostScript name, collection face index, text, size, spacing and bounding box in `cover.json`; recording these does not grant a font license.

The renderer requires saved cells and an explicit reference. Default name lettering additionally requires existing authorized PingFang SC Light; it never downloads a font. No other skill, image generation, segmentation or Lumina is required. A minimum original long side of 512 rejects tiny logical grids, but does **not** verify identity or prove the file is original art. Visual and provenance checks remain mandatory.

## Acceptance and delivery

Inspect the unblurred reference/crop, full cover and a face/detail view. Verify matching identity/costume, full crisp foreground, correct orientation, visible eyes/outlines, preserved white beads/internal holes/detached pieces, readable bead texture and a background that stays subordinate while retaining recognizable character/scene structure. Check top/bottom and side transitions for visible rectangular edges; avoid featureless oversized face fragments. Review the character name for spelling, font coverage, legibility, balanced spacing and separation from the subject. Keep rim light subtle, outside bead pixels and internal holes. Avoid prominent source lettering in the background crop. Adjust background framing/blur before changing the subject scale. A small-cell pattern may need gentler relief or `--flat`.

`cover.json` records exact input/output hashes, layout, reference source/check and counts derived from cells; `background_framing` additionally records the uniform scale, visible source region/fraction and canvas placement. Its initial status is `cover_ready_for_review`. A generated sample, including one rendered on an authorized Mac, is for aesthetic feedback and does not imply user acceptance. After the user's visual acceptance, record concise checks there and set its status to `accepted`. Retain the layers internally; show and link only `封面.png` as the extra cover image alongside the required chart files. For a cover-only task, deliver the cover without duplicating the old chart files. When validating an implementation, compare input hashes and chart delivery hashes before/after, not only counts. For a background-only revision, also compare foreground PNG hashes. When changing the subject's display scale, compare the logical cell-center RGBA values at each integer scale instead of expecting identical foreground PNGs. Keep the previous cover for side-by-side review.
