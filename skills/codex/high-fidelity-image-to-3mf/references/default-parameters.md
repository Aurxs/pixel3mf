# Default Parameters

Use these values unless the user overrides them. Treat this file as the single source of truth for defaults.

## Image preparation

- Route: infer `generate`, `reference-guided`, or `direct-conversion`
- Style: detailed continuous-tone raster; preserve antialiasing, gradients, texture, and smooth geometry
- Canvas: square
- Background: transparent for an isolated subject; preserve an intentional scene
- Source: retain the original upload unchanged
- Resampling: use a high-quality filter only when necessary
- Perfect Pixel and logical-grid processing: disabled

## Lumina

- Physical size: `65 mm × 65 mm`
- Backing thickness: `1.2 mm`
- Structure: `Double-sided`
- Hanging loop: disabled
- LUT: `Lumina-Layers/lut-npy预设/bambulab/Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy`
- Color mode: detect from the LUT; this preset currently resolves to `RYBW`
- Modeling mode API value: `high-fidelity`
- Core enum: `ModelingMode.HIGH_FIDELITY`
- Quantization colors: `256`; pass explicitly to preview and conversion, including CLI/API and fallback paths. This is a fixed parameter, not a requirement for 256 distinct colors; never lower it automatically. The separate 18-color bead workflow is unchanged.
- Hue weight: `0.4`
- Isolated-pixel cleanup: enabled
- Batch conversion: preferred, including one-image batches
- 2D preview: required before 3MF generation

The current checkout processes high-fidelity images at about `10 px/mm`, so the default square is approximately `650 × 650` processing pixels. Verify and record the runtime result instead of imposing this as an upstream resize.

## Retention

- Run folder: `output/<timestamp>_<slug>/`
- Keep the original source, prepared images, preview, batch archive, 3MF, and manifest.
- Preserve Lumina-generated project and slicing metadata; do not rewrite printer, layer, bed, filament, or machine G-code settings.
