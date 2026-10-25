---
name: high-fidelity-image-to-3mf
description: Generate, edit, prepare, or directly convert a detailed raster image into a printable layered 3MF with the local Lumina-Layers checkout. Use for text-described subjects, reference-guided image creation, photos, illustrations, renders, or other continuous-tone inputs that must retain smooth edges, gradients, texture, and high-resolution detail through Lumina high-fidelity mode. Research official sources before generating or creatively editing a recognizable character, mascot, or branded figure. Do not use for logical-grid pixel art or Perfect Pixel workflows; use pixel-art-to-3mf instead.
---

# High-Fidelity Image to 3MF

Run a detailed raster source → Lumina high-fidelity preview → layered 3MF workflow.

## Runtime portability

Use the current Pixel3MF project root. Command examples use POSIX syntax; on Windows use `.venv/Scripts/python.exe`, PowerShell-compatible quoting and one-line commands instead of backslash continuations. Never copy another computer's virtual environment.

## Inputs and route

Accept a subject description, character name, or image.

- **Generate**: create a new detailed target from text.
- **Reference-guided**: create or edit a target using an image for the properties the user names.
- **Direct conversion**: convert the uploaded image itself without creative redesign.

Infer the route from the request. Treat “use this as a reference” as reference-guided and “convert this image” as direct conversion. Ask only when choosing incorrectly would materially change the image. Preserve an uploaded source unchanged in the run folder.

## Character research

Before generating or creatively editing a recognizable character, mascot, or branded figure:

1. Search official or first-party sources for canonical identity and appearance.
2. Save `00_official_character_research.md` with the canonical version, source URLs, verified visual traits, and clearly labeled inferences.
3. Use that brief as the identity authority without copying logos, slogans, or long source text.

Perform this once per run and reuse the brief for retries. Update it only if the requested identity or version changes. If reliable official information is unavailable or the identity is ambiguous, use an approved user reference or ask before generating. For original subjects and direct conversion, record `official_character_research_status: not_applicable` in the manifest; no research file is required.

## Required references

- Read [default-parameters.md](references/default-parameters.md) for the authoritative defaults.
- Read [generation-prompt.md](references/generation-prompt.md) before generating or editing an image.
- Read [workflow.md](references/workflow.md) before running the pipeline.
- Read [troubleshooting.md](references/troubleshooting.md) only after an acceptance or conversion failure.

## Hard boundaries

- Preserve continuous-tone detail, antialiasing, smooth contours, gradients, texture, and natural high-resolution geometry.
- For direct conversion, make only conversion-required derivatives unless the user requests creative edits.
- Do not use Perfect Pixel, logical-grid detection, nearest-neighbor enlargement, coarse-density thresholds, or pixel cleanup.
- Do not call project wrappers that silently impose pixel-specific stages or `modeling_mode=pixel`.
- Use the exact API value `modeling_mode=high-fidelity` or core enum `ModelingMode.HIGH_FIDELITY`.
- Generate and inspect the Lumina 2D preview before the 3MF.
- Preserve Lumina's generated 3MF project and slicing metadata.

## Execution summary

1. Select the route, preserve the source, and complete character research when required.
2. Generate, edit, or accept the high-fidelity target; inspect identity, composition, artifacts, and usable resolution.
3. Preserve intentional backgrounds; otherwise remove the background when appropriate and prepare a square high-fidelity working image.
4. Resolve the LUT and color mode from the current Lumina checkout, then generate and inspect the 2D preview.
5. Convert with Lumina high-fidelity mode, preserve the batch archive, and extract the final 3MF.
6. Save the manifest and return the prepared image, preview, final 3MF, and relevant warnings.

Use a new `output/<timestamp>_<slug>/` folder for every run and retain intermediate artifacts. Follow the filenames and manifest fields in [workflow.md](references/workflow.md).

## Implementation guidance

When asked to automate the workflow, create a separate high-fidelity entry point or parameterize genuinely shared utilities. Reuse source preservation, segmentation, square padding, LUT discovery, preview/conversion, archive extraction, and manifest handling. Exclude Perfect Pixel and all other pixel-only behavior. Inspect current Lumina APIs and enums instead of guessing parameter names.
