"""Small installation smoke check; no models or conversions are run."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "Lumina-Layers"))


def main() -> None:
    import fastapi  # noqa: F401
    import onnxruntime  # noqa: F401
    import perfect_pixel  # noqa: F401
    import psutil  # noqa: F401
    import rembg  # noqa: F401
    import uvicorn  # noqa: F401
    import run_pipeline  # noqa: F401
    import workbuddy_pixel3mf
    from config import PrinterConfig
    from lumina_batch import LUT_FILENAME

    if abs(float(PrinterConfig.NOZZLE_WIDTH) - 0.42) > 1e-9:
        raise RuntimeError("Lumina NOZZLE_WIDTH must be 0.42 mm")
    matches = list((ROOT / "Lumina-Layers" / "lut-npy预设").rglob(LUT_FILENAME))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one required LUT, found {len(matches)}")
    if not (ROOT / "profiles" / "bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json").is_file():
        raise FileNotFoundError("Missing bundled A1 mini profile")
    if not workbuddy_pixel3mf.GENERATION_PROMPT_PATH.is_file():
        raise FileNotFoundError("Missing WorkBuddy anime generation prompt")
    print("Environment check passed (imports, LUT, nozzle and A1 mini profile).")
    print("This check does not download segmentation weights or perform a conversion.")


if __name__ == "__main__":
    main()
