# Stage 2 — Source Acceptance

Do not read this file until `01_source.png` exists. These rules are diagnostics for the completed source and are never image-generation prompt content.

## Generated-source gate

Inspect the completed image before accepting it:

- Compare its visible cell size and information density with the bundled coarse-density references.
- Run Perfect Pixel auto-detection as a diagnostic.
- Require `60–85` detected cells per axis, inclusive.
- Reject when either axis is below `60` or above `85`.
- Never resize, resample, sharpen, add detail, or force a grid to enter the accepted range.

Reject and generate a brand-new source when any of these defects appears:

- The portrait extends below the upper chest, sits too low, minimizes the head, or touches the canvas bottom.
- The source resembles a polished illustration or contains fine hair strands, micro-texture, mixed cell sizes, gradients, antialiasing, or insufficiently large color blocks.
- The default pose becomes flatly frontal or full profile, hides an eye, or loses readable three-quarter depth.
- The eyes use different top/bottom rows or different iris/pupil row counts, their centers or gaze do not align, or the far eye is shorter or more than one logical cell narrower. Ignore sclera-only occlusion when judging eye height.
- The neck becomes a long narrow connector or the head looks detached from the collar and shoulders.
- The exterior pure-black outline is open, the bottom-most occupied row is not a continuous black baseline, or no clean background row remains below it.

## Rejection and retry

- Start a fresh Stage 1 generation from the original request, approved identity brief, bundled references, and original user references.
- Do not use the rejected generated image as an edit target, attached reference, or recent-image context.
- Rebuild the retry exclusively from the fenced generation block in `generation-prompt.md`.
- Do not put detected counts, the accepted range, Perfect Pixel terminology, physical dimensions, or conversion settings into the retry prompt.

## User-provided source

- Preserve the source when the user requested direct conversion.
- Edit it only when the user explicitly requested a local creative correction.
- If it fails the gate and editing was not authorized, report the limitation and obtain acceptance before refinement rather than silently changing it.

Record the detected grid, gate result, and rejection reason in the run metadata.
