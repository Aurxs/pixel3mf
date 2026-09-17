# Pinned official project-settings structure

`bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json` is the complete flattened `project_settings.config` structure used for final 3MF normalization.

It was derived from Bambu Studio 02.07.01.62's installed official profiles for:

- Bambu Lab A1 mini 0.4 nozzle
- `0.08mm Extra Fine @BBL A1M`
- Bambu PLA Basic on A1 mini

The selected preset IDs remain the exact official IDs. Pixel3mf-specific process values are stored as project-level overrides, including a 170 mm prime tower with a 1 mm brim at `X=5, Y=160`; they do not create custom printer, process, or filament presets. Bambu Studio can therefore compare the project values with the official process and reset individual changes.

The `different_settings_to_system` vector follows Bambu Studio's `process + N filaments + printer` layout. Only its process element lists changed keys; every filament and printer element is empty. Without that list, Bambu Studio reloads the official process values over the flattened project values when the 3MF opens.

Only the data that must come from Lumina is copied from its project: dynamic colours, colour/extruder mapping, and the first source `N×N` flush matrix. The A1 mini machine and Bambu PLA Basic identities and parameters stay on the pinned official Bambu Studio baseline. Keeping the flattened structure in the outer repository makes export deterministic and avoids a runtime dependency on Bambu Studio or edits inside `Lumina-Layers/`.

When intentionally refreshing the snapshot for a newer Bambu Studio release, re-run the 3MF normalization tests and slice both a real `2×2` and `3×3` output before replacing this file.
