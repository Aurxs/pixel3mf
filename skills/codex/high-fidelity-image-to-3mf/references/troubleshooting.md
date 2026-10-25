# Troubleshooting

## The target became pixel art

- Remove logical-grid, coarse-density, limited-palette, and nearest-neighbor instructions.
- Do not load pixel-art style references or run Perfect Pixel.
- Confirm `modeling_mode=high-fidelity` in both preview and conversion.

## The wrong input route was used

- If a direct source was redesigned, restore the untouched original and rebuild only required derivatives.
- If a reference was converted directly, identify the properties the user wanted transferred and create a separate target.
- Keep the selected route and provenance explicit in the manifest.

## Background removal damages detail

- Prefer existing alpha, then tune segmentation.
- Preserve intentional full-frame backgrounds.
- Avoid color-key removal around white hair, clothing, glow, or highlights.
- Compare edge alpha and interior holes against the source at high zoom.

## The source is too small

- Compare it with Lumina's current runtime processing dimensions.
- Regenerate a generated/reference-guided target at higher resolution.
- For direct conversion, disclose the limitation and ask before generative enhancement.

## Preview loses detail or shifts color

- Confirm the LUT, detected `color_mode`, and configured parameters.
- Compare cleanup enabled/disabled only if it removes meaningful small features.
- Change one variable at a time and regenerate the preview.

## Lumina rejects a mode or parameter

- Inspect the current API schema, modeling enum, and `LUTManager`.
- Use `high-fidelity` for the API or `ModelingMode.HIGH_FIDELITY` for core calls.
- Resolve the LUT display name and `color_mode` instead of guessing.

## Batch or 3MF handling is wrong

- Preserve a returned ZIP before extracting the unique 3MF.
- Do not use wrappers that hard-code pixel processing.
- Leave printer and slicing metadata unchanged for later review in Bambu Studio.
