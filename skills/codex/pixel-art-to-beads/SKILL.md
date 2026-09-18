---
name: pixel-art-to-beads
description: Generate coarse pixel art from text or image references, or read existing pixel art, and create usable bead patterns with MARD color codes, accurate bead counts, normal and horizontal-mirror charts, printable PDF and editable data. Use for 拼豆图纸、像素画转拼豆、正常和镜像图纸. Self-contained; does not require any other skill or the pixel3mf/Lumina project.
---

# Pixel Art to Beads

Create two readable charts on every successful run: **正常版.png** and **镜像版.png**. Mirror the cell matrix horizontally, then render upright labels and coordinates. Both variants use the same bead counts for **one** physical work, not double quantities.

## Scope and independence

All instructions, prompts, style assets, palette data and scripts live in this directory. Resolve their paths from this SKILL.md, not the current working directory. Do not invoke, read or import another skill at runtime. No Lumina, 3MF, printer profiles, external platform automation or service account is required. Image generation uses the host's available image tool; Python packages and a CJK TrueType font are ordinary declared runtime dependencies. See [runtime.md](references/runtime.md) when choosing an interpreter or resolving missing packages.

## Select the route

- **New artwork:** text, subject photo, character reference or requested creative edit -> generation, lightweight inspection, Perfect Pixel, final visual review, bead mapping.
- **Existing logical PNG:** one actual pixel per intended bead, including final grids from previous work -> skip generation and grid detection; pass directly to the chart tool. Do not mistake an enlarged preview for this file.
- **Enlarged pixel art:** recover its logical grid with the preparation tool, inspect, then map.
- **Saved pattern JSON:** re-render without image generation, grid detection or recoloring.
- A photograph is a subject reference for new pixel art. A chart screenshot with printed codes/watermarks is a layout reference, not clean pixel input. Screenshot/OCR reconstruction is outside this version; request the clean pixel source if necessary.

Keep the user's provided original unchanged. A request to reuse artwork does not authorize redesign. Preserve explicit size, background, pose and palette choices. Missing routine preferences use the defaults below rather than an approval gate.

## Stage 1: Generate only if needed

Read [generation.md](references/generation.md), inspect authorized references and record `00_subject_brief.md` in a fresh run directory. Named recognizable characters use first-party research for canonical details. Generate a pixel source using the fenced prompt and save `01_source.png`.

Keep generation context separate: do not put color-card codes, matching metrics, bead counts, PDF typography or downstream error logs in the image prompt. Attach actual image references through the image tool. Do not ask the image model to draw the numbered bead chart.

Inspect that the subject and framing are present. Raw gradients, antialiasing, partial alpha or imperfect block edges go through refinement before final judgment. For a wrong subject or missing major content, retry from the original inputs, at most twice for the same failure. Do not attach a rejected generated result as a new reference. Preserve failures; do not claim an unaccepted candidate is finished.

## Stage 2: Prepare and review the logical grid

Once an image exists, read [preparation.md](references/preparation.md). Run the bundled `scripts/prepare_source.py` on raw/enlarged pixel sources. Known final logical grids bypass this step unless explicit background preparation is needed.

Inspect the resulting preview for identity, silhouette, white subject details, intentional holes and background correctness. Default to preserving the input background; new isolated subjects prefer genuine transparent alpha. Never globally erase white or silently manufacture a fixed 50×50 grid. Grid detection failure needs source review, not a forced density pass.

## Stage 3: Match colors and export

Read [charts.md](references/charts.md). Use `scripts/bead_pattern.py` on the accepted logical PNG. The default is the bundled MARD 221 community palette; do not invent brand codes or claim manufacturer-certified RGB. For a supplied palette, follow [palette-format.md](references/palette-format.md).

Defaults: preserve logical dimensions; transparent cells are empty; opaque white is a bead; no dithering; no fixed color cap; every 5 cells has a major line; produce both variants plus PDF/CSV/JSON. If the user asks for a full background, select an explicit valid background code. Do not fill an intentional subject hole without the user's requested background mode supporting it.

Preserve the pre-mapping source and render a nearest-neighbor preview of the mapped result. Check important outlines, eyes, skin and accessories for unwanted color merges. If a cap damages recognition, adjust allowed/locked colors or explain the tradeoff; do not repaint the source silently. Disconnected occupied components are listed in JSON; visually review and disclose detached pieces, without automatically drawing connecting beads.

## Stage 4: Focused acceptance and delivery

Inspect normal and mirrored charts at full view and a representative label crop. Inspect the PDF overview and one detail page when tiled. Check counts, mirrored positions, upright text and page coordinate ranges. The script reports `rendered_needs_visual_review`; only set the project status to `accepted` after visual checks. Record concise checks in `review.json` beside the output. Do not rerun unrelated project tests.

Show the two main charts or their previews and link the normal PNG, mirror PNG, PDF and shared material CSV. Give grid dimensions, colors and total beads; call out significant mapping loss, detached components or unverified aspects. Retain editable JSON and source PNG. Do not require the user to choose normal versus mirror: both are always delivered.
