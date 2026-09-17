# Stage 2 — Lightweight Source Preflight

Read after `01_source.png` exists. This is input triage, not pixel-quality acceptance. Formal review occurs after Perfect Pixel in [pixel-refinement.md](pixel-refinement.md).

## Check what refinement cannot fix

- Confirm the image opens, is nonempty, and contains the requested subject.
- A wrong subject, major missing parts, unintended extra subjects or essential content cropped out can justify a fresh generation.
- Respect the requested composition and reference roles without imposing anime portrait anatomy or crop rules.
- Preserve the original file and record the intended background mode.

Record gradients, near-identical colors, blur, antialiasing, irregular-looking blocks, partial alpha and near-white backgrounds as `pending_refinement`. Do not mark `needs_revision` or regenerate solely for these before trying Perfect Pixel. The prompt's 24×24 and palette targets guide style; they are not exact raw-file acceptance thresholds.

## Select preparation

Use an existing Pillow runtime to inspect dimensions and alpha. This selects processing, not final acceptance:

- **Real transparency, including partial alpha:** carry alpha into Perfect Pixel, then binarize sampled logical-cell alpha and inspect for lost subject parts. Do not reject partial alpha or composite the source onto white.
- **Opaque plain background:** use general-subject segmentation if a cutout is needed. Preserve meaningful white subject regions.
- **Painted checkerboard or complex unwanted background:** record that transparency was not generated. Perfect Pixel does not remove backgrounds; use a reviewed semantic mask before final acceptance. If separation fails, explain that specific limitation.
- **Intentional scene/background:** preserve it as content unless removal is requested.

Ignore hidden RGB under alpha 0. Do not infer transparency from the viewer backdrop. Proceed to Stage 3 for finished PNG and 3MF requests. If the user explicitly requested only raw generation without processing, deliver it as `unrefined`, not as having passed final pixel acceptance.

## Direct inputs

Preserve user originals and write derived outputs separately. Direct conversion authorizes necessary refinement, not creative redesign. Ordinary photos requested for direct conversion belong to the high-fidelity workflow unless pixel-art reinterpretation was requested.
