# Character covers

## Visual construction

Use a 3:4 portrait canvas (1080×1440). Keep a broad view of the original character artwork retained during generation/research: default to proportional `contain` at zoom 1.0, preserving the complete selected reference region. Gaussian-blur by about 1.6% of canvas width, use background brightness 0.86 and saturation 0.88, and retain its original color relationships. This is a modest lift from the previous 0.78 brightness; do not brighten by adding a white veil or washing out colors. Softly fill any margins with a more blurred version of the same reference; the canvas stays full without stretching or hard letterbox edges. Avoid a tightly cropped giant face or flat color fields. Center the unchanged, tightly cropped uncompressed pixel artwork at about 60% of canvas width and up to 52% of height, leaving more scene artwork visible around it. Use nearest-neighbor integer scaling, preserving every source RGBA pixel. Do not add bead grids, fused-square relief, artificial highlights inside pixels, palette repainting or smoothing. A soft shadow may sit outside the foreground. Keep the entire subject visible. Place the reviewed Chinese name as `「角色名」` below the subject in plain white PingFang SC Light, with a clear gap and no overlap. Do not add a text gradient, outline or shadow. Add a subtle diffuse rim light outside the silhouette, as in the supplied cover reference; keep pixel steps sharp, avoid a thick white outline, and exclude internal holes from the glow. No slogan, signature or watermark; adjust placement by visual review.

The background is the **user-supplied full-scene illustration**, or matching official scene artwork retained during research, never our pixel source, mapped preview or bead chart. Prefer the character in its environment, such as the supplied Suzuran Spring Praise forest illustration; a standalone cutout or collage is not equivalent. User-supplied scene artwork takes precedence over an earlier research reference. Inspect it before use and verify the same character and costume against the subject brief/research. Crop unrelated reference sheets to the matching character while retaining nearby scenery and excluding unrelated panels or prominent lettering. Preserve the environment and intentional companions in a coherent scene illustration. Do not crop to only the face and then enlarge it again to fill the portrait. Crop coordinates refer to the EXIF-oriented original. Keep the original file unchanged. Record its source URL/research path and the identity/costume check. Do not fetch a different costume simply because it is easier to fill the canvas. If the retained reference is missing, first recover it from that run's recorded source; if unavailable, report the missing input.

The foreground comes directly from the **accepted uncompressed original logical PNG before bead-palette mapping**, in its original orientation. Use saved chart JSON to verify grid size/occupancy and retain chart statistics, not to reconstruct the pixels from color codes. The workflow uses `work/00_source.png` by default, or the recorded original logical source when needed; `--foreground` selects it explicitly. Only crop transparent outer padding and enlarge by nearest-neighbor integer scaling. Do not recolor, quantize, smooth, add grids/bead relief, fill holes, connect pieces, mirror or regenerate it. A compressed cover requires an explicit user request; an accepted compressed chart does not replace this default. The deterministic compositor writes new cover artifacts without changing source inputs.

## Existing workflow

Resolve `PYTHON` and `TOOLS_DIR` via [runtime.md](runtime.md). After chart export/review:

```bash
"$PYTHON" "$TOOLS_DIR/run_workflow.py" cover /absolute/run \
  --variant uncompressed \
  --foreground /absolute/run/work/00_source.png \
  --reference /absolute/original_character_reference.jpg \
  --reference-note '已核对：与本次角色及默认服装一致，复用生图时官方原画' \
  --reference-source 'https://official.example/retained-source.jpg'
```

This creates `run/covers/cover/封面.png`, internal `前景.png` and `背景.png`, and `cover.json`. The character name defaults to the saved project title; use `--name-text` for a verified short name if the historical title includes extra outfit/metadata wording. The workflow manifest, source JSON, palette, previews, counts and every file in `delivery/` remain unchanged. `expected_primary_products` stays two/four. The cover is an additional presentation image outside `delivery/`.

Use `--variant compressed` only if explicitly requested and that exported variant exists and has passed visual review. Never choose it merely because it was the last reviewed output. Use `--name cover-2` for a new attempt; existing output directories are never overwritten. A cover attempt does not accept the charts automatically.

## Saved chart outside a workflow

For historical chart projects, use the same compositor directly; do not regenerate their charts:

```bash
"$PYTHON" "$TOOLS_DIR/render_cover.py" \
  /absolute/图纸数据.json /absolute/new_cover_directory \
  --foreground /absolute/accepted_uncompressed_logical.png \
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
- `--foreground /absolute/original_logical.png`: preserve original RGBA pixels without bead-palette repainting; dimensions and occupancy must match the selected variant.
- `--flat`: compatibility option; original pixels are already flat by default.
- `--bead-texture`: saved-cell relief only on explicit request, incompatible with original-PNG foreground mode. Never add it for the default cover.
- `--name-text '中文角色名'`: reviewed character name; defaults to saved project title. The default style adds `「」` exactly once; already quoted input also works. Never translate or invent a name. `--no-name` explicitly restores text-free covers.
- `--name-style pingfang_light`: default, plain white PingFang SC Light. At 1080×1440 use initial size 48 pixels, tracking 6 pixels and ink center (540, 1138); scale proportionally with the canvas. Text must remain below the subject, with at least 2.5% of canvas height as clear gap and no overlap. The name is 20% larger than the earlier 40-pixel sample; retain the subject and background layout.
- `--name-size 0.044444444`: optional font size / canvas width (default 48/1080 for PingFang), automatically reduced for a long name. Clipping and unsupported glyphs fail before publishing outputs.
- `--name-font /absolute/existing-font.ttc`: existing authorized TTF/OTF/TTC path. For the default style the file must contain the exact PostScript face `PingFangSC-Light`; the renderer locates its collection index instead of assuming face zero. Without a path, inspect local macOS PingFang locations or fontconfig and verify the actual face. A fontconfig fallback never counts as PingFang.
- `--glow 0.40`: subtle diffuse light outside the character silhouette. Use `--glow 0` to disable it; it never changes the saved foreground or chart cells.

## Name style and font license

The default uses the environment's existing PingFang SC Light (`PingFangSC-Light`) with corner quotes, plain white ink and gentle spacing. Prefer the user's familiar Chinese name; use `--name-text` when the project title includes a full surname, date or costume label that would make an awkward cover name. Long names shrink within the safe width. Font identity, all name glyphs and both quote glyphs must pass checks. Missing font, missing glyphs or an impossible fit are visible errors; do not silently substitute or present an alternative as PingFang. Report the exact font/glyph requirement and keep the named cover pending. Existing charts remain deliverable. Use an authorized Mac's local system font if available; do not copy, extract, upload, download from unofficial mirrors or package Apple font files in the repository or skill. The renderer reads the selected font locally and writes only raster images and provenance.

The earlier warm calligraphic style remains available only through explicit `--name-style warm_calligraphic`, when requested. It uses the unmodified `assets/fonts/LXGWWenKaiLite-Regular.ttf`, bundled with upstream `OFL.txt` and `source.json` (source URL, pinned revision and SHA-256), or an explicitly supplied licensed font. It is not a fallback for missing PingFang. Keep the full SIL OFL 1.1 notice/source record with redistributed WenKai bundles. Custom font permission must be verified separately. Runtime records the actual font hash, family, style, PostScript name, collection face index, text, size, spacing and bounding box in `cover.json`; recording these does not grant a font license.

The renderer uses saved chart JSON for validation, an original logical PNG for the default foreground and an explicit scene reference for the background. Default name lettering additionally requires existing authorized PingFang SC Light; it never downloads a font. No other skill, image generation, segmentation or Lumina is required. A minimum original long side of 512 rejects tiny logical grids, but does **not** verify identity or prove the file is original art. Visual and provenance checks remain mandatory.

## Acceptance and delivery

Inspect the unblurred reference/crop, full cover and a face/detail view. Verify matching identity/costume, full crisp original-pixel foreground, correct orientation, visible eyes/outlines, preserved colors/alpha/internal holes/detached pieces, no bead-grid or relief treatment and a background that stays subordinate while retaining recognizable character/scene structure. Check top/bottom and side transitions for visible rectangular edges; avoid featureless oversized face fragments. Review the character name for spelling, font coverage, legibility, balanced spacing and separation from the subject. Keep rim light subtle, outside bead pixels and internal holes. Avoid prominent source lettering in the background crop. Adjust background framing/blur before changing the subject scale. Do not improve facial details or add surface treatment during composition; the source pixel artwork is the finished foreground.

`cover.json` records the foreground PNG path/hash, transparent-border crop and nearest-neighbor scale, as well as input/output hashes, layout, reference source/check and chart counts derived from cells; `background_framing` additionally records the uniform scale, visible source region/fraction and canvas placement. Its initial status is `cover_ready_for_review`. A generated sample, including one rendered on an authorized Mac, is for aesthetic feedback and does not imply user acceptance. After the user's visual acceptance, record concise checks there and set its status to `accepted`. Retain the layers internally; show and link only `封面.png` as the extra cover image alongside the required chart files. For a cover-only task, deliver the cover without duplicating the old chart files. When validating an implementation, compare input hashes and chart delivery hashes before/after, not only counts. For a background-only revision, also compare foreground PNG hashes. For original-PNG mode, compare every RGBA value of the foreground layer against the transparent-cropped source enlarged by nearest-neighbor integer scaling. Cell-center agreement alone would miss an added grid or relief border. Keep the previous cover for side-by-side review.
