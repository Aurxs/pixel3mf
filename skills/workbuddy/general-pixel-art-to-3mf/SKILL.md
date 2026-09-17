---
name: general-pixel-art-to-3mf
description: Create coarse pixel art of general subjects from text, reference images, or real-world photos, then optionally export printable layered 3MFs with the local pixel3mf and Lumina-Layers pipeline. Use for people, pets, plants, objects, vehicles, buildings, or compact scenes without anime portrait constraints. Accept existing pixel art for direct conversion. Use the separate high-fidelity workflow when photographic detail or smooth rendering must be retained.
---

# General Pixel Art to 3MF

Turn a user-described subject or photographed subject into readable coarse pixel art. Support text-only generation, reference-guided generation, explicit image edits, and direct conversion of existing pixel art. This skill has its own generation and acceptance rules. Bundled examples demonstrate pixel style only; never import their character identity or anime portrait anatomy.

## Runtime portability

Use the current Pixel3MF project root. Command examples use POSIX syntax; on Windows use `.venv/Scripts/python.exe`, PowerShell-compatible quoting and one-line commands instead of backslash continuations. Never copy another computer's virtual environment.

## Select the route

- **Text to pixel art:** infer the composition from the requested subject and intended use.
- **Reference/photo to pixel art:** inspect the supplied images and generate a new pixel-art interpretation. A real photo supplies visible appearance, proportions, colors, markings, or composition; it is not already a pixel-grid source.
- **Explicit edit:** edit a user image only as requested, retaining unrelated content.
- **Direct conversion:** preserve existing pixel art and skip generation. If the user requests direct conversion of an ordinary photograph without redrawing, use the separate high-fidelity workflow; do not silently pixelate it or send it into Perfect Pixel.

“参考这张照片做像素画” authorizes a new interpretation. “原图直接转 3MF，不要重画” requests direct conversion. Ask only when the route cannot be inferred and would materially change the result.

Respect the requested endpoint: a finished pixel PNG goes through Perfect Pixel and final acceptance, then stops before Lumina. A raw-generation-only request stops after lightweight inspection and is reported as unrefined. Do not reject raw sources merely for gradients, antialiasing, extra colors, irregular-looking blocks, or partial alpha; evaluate pixel quality on the refined result. Continue to export when 3MF is requested.

Generate on a uniform pure-white, fully opaque background in WorkBuddy. Do not request transparent generation or pass transparency parameters. Remove background locally only after a source exists; preserve intended white subject details.

## Stage boundaries

Keep generation separate from downstream conversion. Read this entrypoint completely, but load supporting references only when needed:

1. **Generate:** read only [generation-prompt.md](references/generation-prompt.md), inspect the authorized input images, and prepare `00_subject_brief.md`. Render the appropriate fenced prompt using the user's request and observed reference attributes. Do not load pipeline scripts, later-stage references, or old manifests before the first source exists. Never put detector thresholds, physical dimensions, LUTs, or slicing settings into image-generation prompts. Save the returned image as `01_source.png`.
2. **Lightweight preflight:** after the source exists, read [source-acceptance.md](references/source-acceptance.md). Check that the file opens and the requested subject and essential composition are present. Record rendering/background problems as preparation notes, not final quality failures.
3. **Refine and accept:** read [pixel-refinement.md](references/pixel-refinement.md). Run Perfect Pixel on the source or necessary background-prepared derivative. Retain the automatically detected grid and produce a binary-alpha logical image and nearest-neighbor preview. Only now judge pixel quality, subject preservation and background correctness. Use general segmentation only when background removal is needed.
4. **Export:** only after `04_pixel_perfect.png` and `05_pixel_preview_8x.png` pass inspection, read [lumina-conversion.md](references/lumina-conversion.md). Export both `2×2` and `3×3` variants with the existing project defaults and retain their previews, archives, and manifests.

For direct conversion, retain the untouched original file with its extension and create a lossless decoded `01_source.png` derivative if needed. Start at Stage 2. Never overwrite a user source.

Use a fresh `output/<timestamp>_<subject-slug>/` run directory and keep intermediate artifacts. Regenerate early only for wrong subject or major missing/cropped content. For rendering defects, attempt Perfect Pixel before deciding whether a fresh source is needed. Retries use the original request, bundled style images, and authorized original subject references, never a rejected generated image. Allow at most two fresh retries for the same failure. Each retry addresses one observed visual defect using the generation template's correction field; repeating an unchanged text-only request is not a corrective strategy. At the limit, record `needs_revision` and show the best candidate as unaccepted rather than reporting success. Keep downstream diagnostics out of retry prompts.

For image inspection, prefer the project's existing `.venv/bin/python`. A worktree may not contain the untracked `.venv`; locate an existing project runtime or the WorkBuddy project's Python/Pillow runtime before falling back to system Python. Missing Pillow in one interpreter is an environment issue, not an image failure. Do not install a duplicate environment just for a PNG check. If numeric inspection remains unavailable, report it as unverified instead of declaring a pass.

## Pipeline integration

Locate the `pixel3mf` project containing `tools/run_pipeline.py` and `Lumina-Layers/`; do not assume the installed skill directory is the project root. This skill packages its own references but relies on that project's existing conversion tools.

Use the individual project tools so final acceptance happens after Perfect Pixel and before Lumina. For the WorkBuddy-generated white-background source, first create a reviewed background-removed derivative using the workspace segmentation tool. Pass that derivative to the packaged helper:

```bash
.venv/bin/python "$SKILL_DIR/scripts/refine_pixel.py" \
  /absolute/path/to/02_bg_removed.png \
  /absolute/path/to/03_working_grid.png \
  /absolute/path/to/03_working_grid_preview_8x.png \
  --png-only --binarize-alpha
```

`--png-only` disables the legacy source-density gate; it does not stop a later, separately requested 3MF export. `--binarize-alpha` thresholds sampled alpha after refinement. Inspect the result for subject loss. Then use `finalize_pixel_grid(..., alpha_policy="preserve", background_rgb=None)` to tight-crop transparent outer rows/columns and produce `04_pixel_perfect.png` and `05_pixel_preview_8x.png`. For other backgrounds, follow the preparation branches in the refinement reference.

The legacy `tools/run_pipeline.py` still enforces the anime workflow's 60–85 source-grid gate and rejects partial source alpha. Do not use it as this general workflow's entrypoint. A detected grid outside that range is not automatically a bad general-subject image. Export the accepted logical grid through `tools/lumina_batch.py`, which sizes from the actual grid. Preserve exact sizing, binary-alpha, ambiguity and geometry checks; never resize to force a density pass.

Keep all stages in one run folder and merge tool metadata into `manifest.json`. Attach generation references through the image tool; the legacy pipeline's `--reference-image` argument only records provenance.

## Deliverables

Record the route, user request, reference paths and roles, visible attributes retained, intentional simplifications, background choice, research status, source path, and result status in `00_subject_brief.md`. For multiple images, distinguish identity/shape, color/material, pose/composition, and style references. Record conflicts and how they were resolved from the user's priorities.

For finished PNG requests, show the refined preview and link the logical PNG plus untouched generated source. For raw-only requests, identify the image as unrefined. For a complete conversion, return the pixel-art preview, both 3MFs with their final physical sizes, and the manifest. Report unsupported or unreadable details honestly rather than claiming a photo-exact reconstruction.

## Example requests

- “根据我家猫的照片生成粗像素画，保留额头花纹和绿眼睛，再转成 3MF。”
- “参考这张实拍，把咖啡机做成像素画，保留轮廓和红色按钮。”
- “第一张是我的房子，第二张只参考像素风格，生成正面像素画。”
- “画一株盆栽仙人掌，只要像素 PNG。”
- “将这张现成像素图直接转成 3MF，不要重画。”


## WorkBuddy host instructions

This is the independent **general-pixel-art-to-3mf** workflow. Use the current Pixel3MF project workspace containing `tools/cleanup_pixel.py`, `tools/lumina_batch.py`, `profiles/`, `.venv/`, and `Lumina-Layers/`. Codex and WorkBuddy share this repository and runtime; their skill variants live in `skills/codex/` and `skills/workbuddy/`. Do not require a separate branch or machine-specific workspace.

### Generation

- Use WorkBuddy's available native ImageGen tool. Inspect its live schema rather than inventing Codex tool names or arguments. A generation request authorizes the first call; keep the common limit of at most two fresh retries for the same failure.
- Read the packaged generation template, render the short pixel-art prompt, and save it beside `00_subject_brief.md`. Native generation may use arbitrary filenames: direct output into a fresh run's `00_incoming/` when supported, then copy the returned local file to `01_source.png` while preserving the original.
- For subject/style images, use the native tool's documented reference-image field. The default style input is the processed corgi, only as a pixel-style reference. Attach user photos separately and label each role. Do not merely place a filesystem path in prompt text and assume the image was attached.
- WorkBuddy generation uses a uniform pure-white, fully opaque background. Do not request a transparent background or pass transparency parameters. Background removal belongs to local postprocessing; preserve white subject features. User-provided direct-conversion files retain their existing alpha.
- Record the actual returned image provider/model, tool arguments excluding secrets, output path and attempt number. Do not label the orchestration model as the image generator. Do not silently switch to TokenHub or another paid provider. If a submitted call has uncertain status, check that call before retrying.

### Refinement and export

- This package includes `scripts/refine_pixel.py` with `--png-only --binarize-alpha`, so it also works with an older WorkBuddy project that lacks these CLI flags. Set `SKILL_DIR` to the absolute path of this installed skill. Run the script with the project's existing Python (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on macOS/Linux); do not install a second runtime or copy generated files into the skill itself.
- For an inspected plain-white source with a closed dark outline and clearly foreground enclosed whites, the workspace exterior-only `white` background method can preserve white fur better than automatic semantics. Inspect any real internal gaps separately; do not use this route to ignore ambiguous holes. Use `isnet-general-use` or a reviewed mask when the background cannot be separated safely.
- After raw-content preflight, run the packaged refinement helper, then the workspace's `finalize_pixel_grid` function and final visual review. Source gradients, partial alpha or a grid outside 60–85 must not cause early regeneration.
- Use the workspace's independent `tools/lumina_batch.py` for both accepted-grid exports, preserving the project's exact geometry and slicer handling. Merge command metadata into the run manifest and keep previews, raw ZIPs and final 3MFs distinct.
- **Do not use `tools/workbuddy_pixel3mf.py`'s `init-run`, `import-candidate`, `decide` or `convert` for this general workflow.** That existing adapter snapshots the anime prompt and performs source rejection before refinement. Likewise do not call the old `run_pipeline.py`. These remain available for the separate anime skill.
- Technical conversion success is not visual acceptance. Compare the refined preview and Lumina previews with the requested subject, especially white features and internal holes. Keep unresolved segmentation ambiguous and stop before conversion rather than ignoring it.

No changes to the user's model selection, account settings, memories or unrelated skills are needed. This ZIP contains workflow instructions, the corgi references and the refinement helper; it requires the already deployed local Pixel3MF/Lumina project and does not bundle model weights or credentials.
