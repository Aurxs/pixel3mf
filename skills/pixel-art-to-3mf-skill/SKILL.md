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
5. Save the returned image as `01_source.png`.

For a defective generated result, start a brand-new generation. Do not pass the rejected image as an edit target, attached reference, or recent-image context. Edit a user-provided source only when the user explicitly asks for a local correction.

### Gate 1

Do not continue until `01_source.png` exists. Until then, do not inspect later-stage documentation or implementation files, even to prepare future steps.

## Stage 2 — Validate the completed source

After `01_source.png` exists, read [source-acceptance.md](references/source-acceptance.md). Apply its visual and diagnostic checks.

- If the source is rejected and regeneration is allowed, return to Stage 1 and preserve the prompt boundary.
- If a user-provided source is unsuitable and creative changes were not authorized, preserve it and report the limitation.
- Do not begin refinement until the source passes or the user explicitly accepts the limitation.

### Gate 2

Record source acceptance before opening the refinement instructions.

## Stage 3 — Prepare and refine pixels

Only after Gate 2, read [pixel-refinement.md](references/pixel-refinement.md). Produce the transparent, aspect-preserving canvas, rectangular refined grid, and preview artifacts described there.

### Gate 3

Do not open conversion settings until the refined pixel artifact and its preview exist.

## Stage 4 — Convert with Lumina and finalize

Only after Gate 3, read [lumina-conversion.md](references/lumina-conversion.md). Derive both exact physical sizes from the same final logical grid, then generate the required `2 × 2` and `3 × 3` Lumina previews, 3MFs, manifests, and retained archives using that stage's defaults. Do not make the user choose a size before export.

## Failure routing

- Failure before `01_source.png`: use only `generation-prompt.md`.
- Failed source acceptance: use only `source-acceptance.md`, then return to the isolated Stage 1 prompt builder if regenerating.
- Background, canvas-preparation, or refinement failure: use only `pixel-refinement.md`.
- Lumina, LUT, archive, or 3MF failure: use only `lumina-conversion.md`.

Never solve a later-stage failure by adding its measurements or settings to the image-generation prompt.
