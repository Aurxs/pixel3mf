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
- Before the first image-generation or image-editing result exists, read [generation-prompt.md](references/generation-prompt.md) and, only for the selected external API route, the model profile it explicitly links. Model profiles contain Stage 1 transport parameters only. Do not open or search any later-stage reference, pipeline script, conversion source, README, manifest from a prior run, or configuration file.
- Build the first image-generation payload from the fenced template in `generation-prompt.md`. On retry, independently rewrite the complete prompt under that file’s Stage 1 rules; do not limit the rewrite to placeholders. Never add instructions, measurements, diagnostics, physical dimensions, conversion settings, or terminology from later stages.
- The image-generation model receives only the Stage 1 visual prompt (rendered initial template or independently rewritten retry), including the requested subject and verified identity summary, plus the allowed original source/style images. Do not forward the complete workflow request or research document. It never receives this `SKILL.md` or any post-generation reference.
- For retries, follow the retry rule in `generation-prompt.md`; keep later-stage information out of generation inputs.

## Route the request

- If no usable source image exists, or the user requests creative generation/editing, start at Stage 1.
- If the user supplies a source for direct conversion without creative editing, save it as `01_source.png`, skip Stage 1, and start at Stage 2.
- Preserve a user-provided source unless the user explicitly requests a creative edit. Do not silently repair or redesign it.

Create a new run folder at `output/<timestamp>_<slug>/` and retain every produced artifact.

## Stage 1 — Create the source image

This is the only stage allowed to call image generation or image editing. Use the backend-selection rules in `generation-prompt.md`: built-in imagegen by default, or the external image API/model explicitly requested by the user. Both routes feed the same subsequent refinement workflow.

1. Read [generation-prompt.md](references/generation-prompt.md). For a selected external API backend, also load only its linked model profile and configuration; do not read later-stage references.
2. Complete its official-character research gate when applicable and save `00_official_character_research.md` before the call.
3. Load only the source/style images authorized by that file.
4. Send the rendered template for the first attempt, or the independently rewritten Stage 1 visual prompt for a retry, as specified in that reference.
5. Save the returned image as `01_source.png`.

For a defective generated result, start a brand-new generation. Do not pass any result image generated in an earlier attempt as an edit target, attached reference, or recent-image context. Reuse of the original official character references, approved user-supplied references, and bundled style references is allowed. Edit a user-provided source only when the user explicitly asks for a local correction.

### Gate 1

Do not continue until `01_source.png` exists. Until then, do not inspect later-stage documentation or implementation files, even to prepare future steps.

## Stage 2 — Validate the completed source

Only after `01_source.png` exists, read [source-acceptance.md](references/source-acceptance.md). Proceed directly to refinement without Agent visual triage or a source review/report. Keep later processing information out of generation payloads.

### Gate 2

Once the source exists, attempt Stage 3 directly. The Agent first reviews the completed refined candidate; do not require a preliminary report or visual verdict. Actual refinement failures follow the retry route.

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
