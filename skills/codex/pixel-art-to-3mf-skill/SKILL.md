---
name: pixel-art-to-3mf
description: Create or prepare a coarse pixel-art character source and convert it into a printable layered 3MF with the local Lumina-Layers checkout. Use for named or recognizable characters, text-described subjects, reference-guided sources, direct source-image conversion, staged source validation, pixel refinement, and Lumina export. Research official sources before generating or creatively editing a recognizable character, mascot, or branded figure.
---

# Pixel Art to 3MF

Follow the stages below in order. Treat every stage gate as a context-loading boundary, not merely as a checklist item.

## Runtime portability

Use the current Pixel3MF project root. Command examples use POSIX syntax; on Windows use `.venv/Scripts/python.exe`, PowerShell-compatible quoting and one-line commands instead of backslash continuations. Never copy another computer's virtual environment.

## Non-negotiable context isolation

- Read this `SKILL.md` completely, but do not preload any file in `references/`.
- Read a reference only when its stage explicitly authorizes it and its prerequisite artifact already exists.
- Before the first image-generation or image-editing result exists, read only [generation-prompt.md](references/generation-prompt.md). Do not open or search any later-stage reference, pipeline script, conversion source, README, manifest from a prior run, or configuration file.
- Build every image-generation payload exclusively from one fenced prompt block in `generation-prompt.md`. Replace placeholders, but do not append instructions, measurements, diagnostics, physical dimensions, conversion settings, or terminology from later stages.
- The image-generation model receives only the rendered prompt block with the requested visual subject and verified identity summary filled into its placeholders, plus the allowed source/style images. Do not forward the complete workflow request or research document. It never receives this `SKILL.md` or any post-generation reference.
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

Only after `01_source.png` exists, read [source-acceptance.md](references/source-acceptance.md). Apply and record its source checks before continuing. Keep diagnostic results out of generation payloads.

### Gate 2

Proceed only after preliminary source acceptance, or explicit user acceptance of a reported limitation. If regeneration is authorized, return to Stage 1 and rebuild its isolated payload.

## Stage 3 — Prepare and refine pixels

Only after Gate 2, read [pixel-refinement.md](references/pixel-refinement.md). Follow its preparation, refinement, and visual-review requirements.

### Gate 3

Proceed only when the required refined artifacts exist and have passed the checks and main-conversation visual review specified in that reference. Resolve rejected results using that stage's failure route.

## Stage 4 — Convert and finalize

Only after Gate 3, and only when conversion is within the user's requested scope, read [lumina-conversion.md](references/lumina-conversion.md). Follow its export and final-delivery requirements.

## Failure routing

- Failure before `01_source.png`: use only `generation-prompt.md`.
- Failed source acceptance: use only `source-acceptance.md`, then return to the isolated Stage 1 prompt builder if regenerating.
- Background, canvas-preparation, or refinement failure: use only `pixel-refinement.md`.
- Lumina, LUT, archive, or 3MF failure: use only `lumina-conversion.md`.

Never solve a later-stage failure by adding its measurements or settings to the image-generation prompt.
