from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from semantic_segment import _providers_for, run_segmentation_model  # noqa: E402


class ProviderTests(unittest.TestCase):
    def test_cpu_uses_only_cpu_provider(self) -> None:
        self.assertEqual(_providers_for("cpu"), ["CPUExecutionProvider"])

    def test_accelerated_devices_are_rejected(self) -> None:
        for device in ("auto", "coreml", "mps"):
            with self.subTest(device=device):
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    _providers_for(device)


class MemoryLimitTests(unittest.TestCase):
    def test_worker_is_killed_after_memory_limit(self) -> None:
        class FakeProcess:
            pid = 123
            returncode = None

            def poll(self):
                return None if self.returncode is None else self.returncode

            def kill(self):
                self.returncode = -9

            def communicate(self):
                return "", ""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"not-read-by-fake-worker")
            with (
                patch("semantic_segment.subprocess.Popen", return_value=FakeProcess()),
                patch("semantic_segment._read_rss_bytes", return_value=2 * 1024**3),
            ):
                with self.assertRaisesRegex(RuntimeError, "exceeded 1 GiB"):
                    run_segmentation_model(
                        source,
                        root / "mask.png",
                        model_name="isnet-anime",
                        device="cpu",
                        memory_limit_gb=1,
                        project_root=root,
                    )


class WorkerFailureTests(unittest.TestCase):
    class _Process:
        pid = 123

        def __init__(self, returncode: int):
            self.returncode = returncode

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def communicate(self):
            return "", "worker crash" if self.returncode else ""

    def test_cpu_worker_crash_is_reported_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"not-read-by-fake-worker")
            with (
                patch(
                    "semantic_segment.subprocess.Popen",
                    return_value=self._Process(-11),
                ) as popen,
                patch("semantic_segment._read_rss_bytes", return_value=0),
            ):
                with self.assertRaisesRegex(RuntimeError, "code -11"):
                    run_segmentation_model(
                        source,
                        root / "mask.png",
                        model_name="isnet-anime",
                        device="cpu",
                        project_root=root,
                    )

            self.assertEqual(popen.call_count, 1)
            self.assertEqual(popen.call_args.kwargs["env"]["NUMBA_DISABLE_JIT"], "1")


if __name__ == "__main__":
    unittest.main()
