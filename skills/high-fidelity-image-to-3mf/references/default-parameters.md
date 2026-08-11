# Default Parameters

Use these values unless the user explicitly overrides them.

## Image preparation

- Input route: infer `generate`, `reference-guided`, or `direct-conversion` from the request.
- Target style: high-fidelity raster with continuous-tone detail; never force pixel art.
- Canvas: square.
- Physical target: `65 mm × 65 mm`.
- Background: transparent for a single isolated subject; preserve an intentional scene/background.
- Source retention: keep the original upload unchanged.
- Resampling: use a high-quality filter only when necessary; do not use nearest-neighbor to create a block grid.
- Perfect Pixel: disabled and omitted.

## Lumina

- LUT filename: `Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy`
- LUT directory family: `Lumina-Layers/lut-npy预设/bambulab/`
- Color mode: detect from the selected LUT; currently `RYBW` for this preset.
- Modeling mode API value: `high-fidelity`
- Core enum: `ModelingMode.HIGH_FIDELITY`
- Quantization colors: `256`
- Hue protection weight: `0.6`
- Isolated-pixel cleanup: enabled
- Target width: `65.0` mm
- Backing thickness: `1.2` mm
- Structure mode: `Double-sided`
- Hanging loop: disabled
- Batch mode: preferred, including for one image
- 2D preview: generate and retain before the 3MF
- Intermediate outputs: always retain

The current Lumina implementation uses `10 px/mm` for high-fidelity raster processing. Expect approximately `650 × 650` processing pixels for the default square target, but verify and record the runtime result because repository behavior may change.

## 3MF project settings

- Preserve Lumina-generated project and slicing metadata.
- Do not rewrite printer model, nozzle, layer heights, first-layer settings, bed geometry, filament mapping, or machine G-code.
- Review printer-specific settings later in Bambu Studio.
