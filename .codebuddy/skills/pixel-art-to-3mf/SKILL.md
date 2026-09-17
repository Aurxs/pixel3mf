---
name: pixel-art-to-3mf
description: Create or prepare a coarse pixel-art character source and convert it into a printable layered 3MF with the local Lumina-Layers checkout. Use for named or recognizable characters, text-described subjects, reference-guided sources, direct source-image conversion, staged source validation, pixel refinement, and Lumina export. Research official sources before generating or creatively editing a recognizable character, mascot, or branded figure.
---

# Pixel Art to 3MF

Follow the stages below in order. Treat every stage gate as a context-loading boundary, not merely as a checklist item.

## Non-negotiable context isolation

- Read this `SKILL.md` completely, but do not preload any file in `references/`.
- Read a reference only when its stage explicitly authorizes it and its prerequisite artifact already exists.
- Before the first image-generation or image-editing result exists, read only [generation-prompt.md](references/generation-prompt.md). Do not open or search any later-stage reference, pipeline script, conversion source, README, manifest from a prior run, or configuration file.
- Build every image-generation payload exclusively from one fenced prompt block in `generation-prompt.md`. Replace placeholders, but do not append instructions, measurements, diagnostics, physical dimensions, conversion settings, or terminology from later stages.
- The image-generation model receives only that rendered prompt block, the original user request, the approved identity brief, and the allowed source/style images. It never receives this `SKILL.md` or any post-generation reference.
- A retry is a new Stage 1 call. Rebuild it from `generation-prompt.md`; never add detector results or later-stage thresholds to its prompt.

## Route the request

- If no usable source image exists, or the user requests creative generation/editing, start at Stage 1.
- If the user supplies a source for direct conversion without creative editing, save it as `01_source.png`, skip Stage 1, and start at Stage 2.
- Preserve a user-provided source unless the user explicitly requests a creative edit. Do not silently repair or redesign it.

Create a new run folder at `output/<timestamp>_<slug>/` and retain every produced artifact.

## Stage 1 — Create the source image

This is the only stage allowed to call image generation or image editing.

1. Read [generation-prompt.md](references/generation-prompt.md). Read no other reference.
2. Complete its official-character research gate when applicable and save `00_official_character_research.md` before the call.
3. Load only the source/style images authorized by that file.
4. Send only the selected fenced prompt block after replacing its placeholders.
5. Save the returned image and register it with `import-candidate`; the candidate is `01_source_attempt_NN.png`. `decide --decision accepted` creates `01_source.png` only after acceptance.

For a defective generated result, start a brand-new generation. Do not pass the rejected image as an edit target, attached reference, or recent-image context. Edit a user-provided source only when the user explicitly asks for a local correction.

### Gate 1

Do not continue until a registered `01_source_attempt_NN.png` (generated) or registered `00_user_source_original.*` (direct) exists. Until then, do not inspect later-stage documentation or implementation files, even to prepare future steps.

## Stage 2 — Validate the completed source

After a registered `01_source_attempt_NN.png` (generated) or registered `00_user_source_original.*` (direct) exists, read [source-acceptance.md](references/source-acceptance.md). Apply its visual and diagnostic checks.

- Treat minor blur, antialiasing, whole-cell tonal transitions, and near-identical colors as recoverable warnings. Let Pixel Fine decide whether they resolve into a stable logical grid.
- If the source is rejected for an unrecoverable grid, composition, or identity defect and regeneration is allowed, return to Stage 1 and preserve the prompt boundary.
- If a user-provided source is unsuitable and creative changes were not authorized, preserve it and report the limitation.
- Do not begin refinement until the source passes. If the user later authorizes a creative correction, start the explicit edit route rather than silently overriding the gate.

### Gate 2

Record the original-size source grid after the permitted native background normalization and preliminary acceptance before opening the refinement instructions. Apply the `60–85` density gate only here, never after semantic masking or temporary padding.

## Stage 3 — Prepare and refine pixels

Only after Gate 2, read [pixel-refinement.md](references/pixel-refinement.md). Produce the semantic mask, temporary working grid, tight export grid, and preview artifacts described there.

### Gate 3

Do not open conversion settings until the refined export artifact and its preview exist, its alpha is binary, and no ambiguous background component remains.

## Stage 4 — Convert with Lumina and finalize

Only after Gate 3, read [lumina-conversion.md](references/lumina-conversion.md). Derive both exact physical sizes from the same final logical grid, then generate the required `2 × 2` and `3 × 3` Lumina previews, 3MFs, manifests, and retained archives using that stage's defaults. Do not make the user choose a size before export.

## Failure routing

- Failure before `01_source.png`: use only `generation-prompt.md`.
- Failed source acceptance: use only `source-acceptance.md`, then return to the isolated Stage 1 prompt builder if regenerating.
- Background, canvas-preparation, or refinement failure: use only `pixel-refinement.md`.
- Lumina, LUT, archive, or 3MF failure: use only `lumina-conversion.md`.

Never solve a later-stage failure by adding its measurements or settings to the image-generation prompt.

## WorkBuddy host adapter

Use this adapter only in WorkBuddy. Keep the core stage order. This adapter and the packaged host reference files define the explicit WorkBuddy differences: candidate filenames, optional references, the Stage 1 canvas grid, and audited near-white normalization.

- The packaged `references/generation-prompt.md` is the WorkBuddy-specific Stage 1 template, maintained in `workbuddy/generation-prompt.md`. Its concise Chinese framing instructions and explicit 64 × 64 canvas grid replace the Codex 24 × 24 visual prior; keep the original source-acceptance rules. New runs snapshot the fenced template; retries use that snapshot. After an explicitly approved prompt change, start a new run instead of rewriting an existing run.
- A research file may include one fenced `identity` block containing only the approved visual identity brief; the renderer uses that block and keeps URLs/audit notes in the saved research artifact.
- Native new-generation tasks default to text-only in the CLI as well as this Skill; `init-run --no-bundled-style` makes it explicit and text-only ImageGen. Use `--with-bundled-style` only when those references are explicitly requested; respect the Stage 1 template.
- `import-candidate` preserves the exact original and normalizes only opaque near-white (all RGB channels >= 240 and channel spread <= 8) background connected to a fully near-white canvas border. This user-approved normalization does not alter enclosed highlights, alpha, dimensions or the grid. Inspect `background_normalization` metadata; all original opacity, source-grid and visual gates still apply afterward.
- Record the actual image tool model in `import-candidate --model` (for the verified native service, text-only uses `hunyuan-image-alpha` and reference-image generation uses `hunyuan-image-alpha-edit`); DeepSeek is the orchestrator, not the image generator.
- Require the active workspace to contain `tools/workbuddy_pixel3mf.py`, `tools/run_pipeline.py`, and `profiles/`. If not, ask the user to switch to the Pixel3MF project workspace.
- Use CLI `--help` for invocation details. Do not inspect implementation scripts or previous runs to calibrate a generation; if rejected, retry within the budget or report the reason.
- Run `.venv/bin/python tools/workbuddy_pixel3mf.py doctor` before the first task in a new installation. Do not make a paid generation request during diagnosis. If credentials are missing, use the interactive `configure-keychain` subcommand; never place a secret in a shell argument or project file.
- For generation or an authorized creative edit, complete the research gate first. Create an official research brief only for a named or recognizable subject; record an original subject as `not_applicable`. Call `init-run`. Prefer `generate` for TokenHub. When TokenHub is not configured, call `render-prompt --json` for the exact prompt, original reference paths, and `output_dir`, invoke WorkBuddy's default image generator exactly once with that rendered prompt and only the registered Stage 1 references, use the returned `output_dir` (`00_incoming/`) for the native tool so its arbitrary filenames cannot block conversion directory ownership checks, then call `import-candidate`. Inspect every objectively passing candidate against Stage 2 and record the result with `decide`. Never exceed three combined attempts and never attach a rejected candidate to a retry.
- If generation reports an uncertain submitted task, call `resume-generation` for the same run; do not call `generate` again. If private COS deletion fails, call `cleanup-references` before generating or converting further.
- For direct conversion, call `init-run --route direct` with `--character-name`, `--character-request` (or its file form), `--request` (or its file form), and `--source-image`, then call `convert`. Preserve the source and follow the Alpha and ambiguity rules in Stage 3.
- Choose the cutout method from the accepted source. For a fully opaque, uniform white-background pixel source with a closed dark outline and clearly identifiable enclosed whites (eyes/highlights, no uncertain background holes), use `convert --background-method white` to preserve the silhouette. Use semantic `auto` for sources requiring hole adjudication. Never use this choice to accept a source that failed Stage 2.
- After conversion, compare `05_pixel_preview_8x.png` against the accepted source for missing colored parts, shoulders, exterior outline and bottom baseline. `status=success` and zero ambiguous white components do not prove silhouette fidelity. If a semantic result deletes real parts from an otherwise suitable simple white-background source, keep that run intact and re-export the exact accepted source in a new direct run using `--background-method white`; retain the original run as generation provenance. Never route a rejected candidate through direct conversion.
- Call `convert` only after one generated candidate is accepted or a direct source is registered. Never pass `--allow-ambiguous-mask`; the WorkBuddy wrapper intentionally does not expose it. If conversion blocks, correct the source or supply an approved binary `--mask-override`, then call `convert` again in the same run; the wrapper archives every failed pipeline attempt.
- Treat `convert` as the deterministic implementation boundary for Stages 3 and 4. WorkBuddy must not preload Lumina reference details into the model context; the wrapper enforces the semantic/ambiguity gate before it invokes Lumina. Inspect and present Stage 3 artifacts only after the command returns, or immediately when it blocks before Lumina.
- Treat WorkBuddy native generation as an explicit temporary provider when TokenHub is unconfigured, not as a silent retry after a submitted or failed TokenHub task. Record it through `import-candidate`, keep the same objective and visual gates, and identify the provider as `workbuddy` in delivery metadata.
- At completion, present `05_pixel_preview_8x.png`, both `06_lumina_2d_preview_*.png` files, both final `08_*.3mf` files, and `manifest.json`. Label `07_lumina_batch_result_*.zip` as raw Lumina archives, not final printable models.
