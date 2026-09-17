from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import workbuddy_pixel3mf as workbuddy  # noqa: E402


def _opaque_png(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    Image.new("RGBA", size, (255, 255, 255, 255)).save(path)


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(payload)

    def json(self):
        return self.payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise workbuddy.requests.HTTPError(str(self.status_code))


class _FakeSession:
    def __init__(self, post_responses: list[_FakeResponse]):
        self.post_responses = list(post_responses)
        self.post_calls: list[dict[str, object]] = []

    def post(self, url, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        return self.post_responses.pop(0)


class WorkBuddyStateTests(unittest.TestCase):
    def test_new_run_pins_prompt_and_defaults_to_no_native_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(character_name="original", character_request="robot",
                                        original_request="robot", route="generate", output_root=tmp)
            _, state = workbuddy.load_state(run_dir)
            prompt = workbuddy.render_prompt(state)
            self.assertEqual(workbuddy.native_reference_files(state), [])
            with patch.object(workbuddy, "_prompt_block", return_value="changed template"):
                self.assertEqual(workbuddy.render_prompt(state), prompt)
            state["use_bundled_style"] = True
            references = workbuddy.native_reference_files(state)
            self.assertEqual(len(references), 3)
            self.assertTrue(all(path.is_file() for path in references))
            self.assertFalse(any(path.name == "style-sheet.png" for path in references))

    def test_local_config_rejects_embedded_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text(
                json.dumps({"tokenhub": {"apiKey": "must-not-be-stored"}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must not contain credentials"):
                workbuddy.load_config(config)

    def test_doctor_remains_callable_when_runtime_imports_are_missing(self) -> None:
        with (
            patch.object(workbuddy, "requests", None),
            patch.object(workbuddy, "Image", None),
            patch.object(workbuddy, "ImageOps", None),
            patch.object(workbuddy, "detect_source_grid", None),
            patch.object(workbuddy, "run_pipeline", None),
            patch.object(workbuddy, "_tokenhub_api_key", return_value=None),
            patch.object(workbuddy, "_cos_credentials", return_value=(None, None)),
        ):
            report = workbuddy.doctor()

        self.assertIn("python_dependencies", report["checks"])
        self.assertIsInstance(report["core_ready"], bool)
        self.assertEqual(report["generation_ready"], report["core_ready"])
        self.assertFalse(report["tokenhub_generation_ready"])
        self.assertEqual(
            report["workbuddy_candidate_import_ready"], report["core_ready"]
        )

    def test_keychain_configuration_uses_interactive_prompt_not_process_argument(self) -> None:
        completed = MagicMock(returncode=0)
        with (
            patch.object(workbuddy.shutil, "which", return_value="/usr/bin/security"),
            patch.object(workbuddy.subprocess, "run", return_value=completed) as run,
        ):
            workbuddy.configure_keychain("tokenhub")

        command = run.call_args.args[0]
        self.assertEqual(command[-1], "-w")
        self.assertNotIn("secret", command)

    def test_completed_research_requires_file_and_official_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "completed research"):
                workbuddy.init_run(
                    character_name="character",
                    character_request="character",
                    original_request="make character",
                    route="generate",
                    output_root=tmp,
                    research_status="completed",
                )

    def test_generation_prompt_comes_only_from_the_fenced_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="original",
                character_request="an original fox waving",
                original_request="make a fox and later print it at 75 mm",
                route="generate",
                output_root=tmp,
            )
            _, state = workbuddy.load_state(run_dir)
            prompt = workbuddy.render_prompt(state)

            self.assertIn("an original fox waving", prompt)
            self.assertIn("64 × 64", prompt)
            self.assertNotIn("24 × 24 pixel-art design as the visual prior", prompt)
            self.assertNotIn("75 mm", prompt)
            self.assertNotIn("60–85", prompt)
            self.assertNotIn("Perfect Pixel", prompt)

    def test_generation_prompt_embeds_the_registered_research_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            research = Path(tmp) / "research.md"
            research.write_text(
                "Canonical jacket: blue. Signature prop: silver staff.\n",
                encoding="utf-8",
            )
            run_dir = workbuddy.init_run(
                character_name="recognizable",
                character_request="recognizable character holding a silver staff",
                original_request="make the character",
                route="generate",
                output_root=Path(tmp) / "output",
                research_status="completed",
                research_path=research,
                official_sources=["https://official.example/character"],
            )
            _, state = workbuddy.load_state(run_dir)

            prompt = workbuddy.render_prompt(state)

            self.assertIn("Canonical jacket: blue", prompt)
            self.assertNotIn(str(run_dir), prompt)

    def test_prompt_uses_only_explicit_identity_block_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            research = Path(tmp) / "research.md"
            research.write_text("Official source: https://official.example/identity\n\n```identity\nGolden hair, amber eyes.\n```\nAudit notes outside the image prompt.\n")
            value = workbuddy._research_prompt_value({"research": {"status": "completed", "path": str(research)}})
            self.assertEqual(value, "Golden hair, amber eyes.")

    def test_edit_prompt_embeds_research_without_postprocessing_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            research = Path(tmp) / "research.md"
            research.write_text("Canonical eye color: green.\n", encoding="utf-8")
            run_dir = workbuddy.init_run(
                character_name="recognizable",
                character_request="recognizable character",
                original_request="fix the far eye",
                route="edit",
                output_root=Path(tmp) / "output",
                source_image=source,
                edit_defect="make the far eye the same height",
                research_status="completed",
                research_path=research,
                official_sources=["https://official.example/character"],
            )
            _, state = workbuddy.load_state(run_dir)

            prompt = workbuddy.render_prompt(state)

            self.assertIn("Canonical eye color: green", prompt)
            self.assertIn("make the far eye the same height", prompt)
            self.assertNotIn("Lumina", prompt)

    def test_state_rejects_tampered_generation_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="original",
                character_request="original",
                original_request="make it",
                route="generate",
                output_root=tmp,
            )
            state_path = run_dir / workbuddy.STATE_FILENAME
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["max_attempts"] = 99
            workbuddy._write_json(state_path, state)

            with self.assertRaisesRegex(ValueError, "must remain 3"):
                workbuddy.load_state(run_dir)

    def test_direct_source_is_preserved_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            original = source.read_bytes()
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )
            _, state = workbuddy.load_state(run_dir)
            preserved = Path(state["source_image"])

            self.assertEqual(preserved.read_bytes(), original)
            self.assertEqual(
                state["source_sha256"], hashlib.sha256(original).hexdigest()
            )

    def test_rejection_reason_is_not_added_to_retry_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="original",
                character_request="an original fox waving",
                original_request="make a fox",
                route="generate",
                output_root=tmp,
            )
            candidate = run_dir / "01_source_attempt_01.png"
            _opaque_png(candidate)
            _, state = workbuddy.load_state(run_dir)
            state["attempts"].append(
                {
                    "number": 1,
                    "file": str(candidate),
                    "objective_validation": {"passed": True},
                    "visual_decision": None,
                    "status": "awaiting_visual_decision",
                }
            )
            workbuddy._write_json(run_dir / workbuddy.STATE_FILENAME, state)
            first_prompt = workbuddy.render_prompt(state)

            workbuddy.decide_source(
                run_dir,
                attempt_number=1,
                decision="rejected",
                reason="detected 90x90 and broken outline",
            )
            _, updated = workbuddy.load_state(run_dir)
            retry_prompt = workbuddy.render_prompt(updated)

            self.assertEqual(first_prompt, retry_prompt)
            self.assertNotIn("90x90", retry_prompt)

    def test_accepting_attempt_copies_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="original",
                character_request="original",
                original_request="make it",
                route="generate",
                output_root=tmp,
            )
            candidate = run_dir / "01_source_attempt_01.png"
            _opaque_png(candidate)
            _, state = workbuddy.load_state(run_dir)
            state["attempts"].append(
                {
                    "number": 1,
                    "file": str(candidate),
                    "objective_validation": {"passed": True},
                    "visual_decision": None,
                    "status": "awaiting_visual_decision",
                }
            )
            workbuddy._write_json(run_dir / workbuddy.STATE_FILENAME, state)

            workbuddy.decide_source(
                run_dir,
                attempt_number=1,
                decision="accepted",
                reason="identity and composition pass",
            )

            self.assertEqual(
                hashlib.sha256(candidate.read_bytes()).digest(),
                hashlib.sha256((run_dir / "01_source.png").read_bytes()).digest(),
            )
            _, updated = workbuddy.load_state(run_dir)
            self.assertEqual(updated["selected_attempt"], 1)


class WorkBuddyGenerationTests(unittest.TestCase):
    def test_native_import_preserves_original_and_enclosed_highlights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "near-white.png"
            image = Image.new("RGBA", (16, 16), (253, 255, 254, 255))
            # Closed red outline isolates a near-white highlight from the background.
            from PIL import ImageDraw
            ImageDraw.Draw(image).rectangle((4, 4, 11, 11), outline=(220, 20, 40, 255))
            image.putpixel((0, 0), (245, 244, 241, 255))
            image.save(source)
            original = source.read_bytes()
            run_dir = workbuddy.init_run(
                character_name="normalization", character_request="original robot",
                original_request="test", route="generate", output_root=Path(tmp) / "runs",
                use_bundled_style=False,
            )
            with patch.object(workbuddy, "detect_source_grid", return_value={"width": 64, "height": 64}):
                result = workbuddy.import_workbuddy_candidate(run_dir, source_image=source)
            self.assertTrue(result["objective_validation"]["passed"])
            metadata = result["background_normalization"]
            self.assertEqual(Path(metadata["original_file"]).read_bytes(), original)
            self.assertEqual(source.read_bytes(), original)
            from run_pipeline import validate_generation_metadata
            _, state = workbuddy.load_state(run_dir)
            state["selected_attempt"] = 1
            validated = validate_generation_metadata(workbuddy._generation_manifest(state))
            self.assertEqual(validated["attempts"][0]["background_normalization"], metadata)
            from datetime import datetime
            from run_pipeline import _prepare_run_dir
            incoming = run_dir / "00_incoming"
            incoming.mkdir()
            (incoming / "native-tool-arbitrary-name.png").write_bytes(original)
            self.assertEqual(_prepare_run_dir(run_dir.parent, "test", datetime.now(), run_dir), run_dir)
            self.assertEqual(metadata["changed_pixels"], 192)
            with Image.open(result["file"]) as normalized:
                self.assertEqual(normalized.size, image.size)
                self.assertEqual(normalized.getpixel((0, 0)), (255, 255, 255, 255))
                self.assertEqual(normalized.getpixel((5, 5)), (253, 255, 254, 255))
                self.assertEqual(normalized.getpixel((4, 4)), (220, 20, 40, 255))

    def test_background_normalization_does_not_hide_alpha_or_border_defects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for color, status in [((253, 255, 254, 200), "skipped_nonopaque"),
                                  ((246, 255, 254, 255), "skipped_nonwhite_border"),
                                  ((0, 0, 0, 255), "skipped_nonwhite_border"),
                                  ((239, 239, 239, 255), "skipped_nonwhite_border")]:
                with self.subTest(status=status):
                    path = Path(tmp) / "source.png"
                    Image.new("RGBA", (8, 8), color).save(path)
                    original = path.read_bytes()
                    result = workbuddy.normalize_generated_background(path)
                    self.assertEqual(result["status"], status)
                    self.assertEqual(path.read_bytes(), original)

    def _run_dir(self, root: str | Path) -> Path:
        return workbuddy.init_run(
            character_name="original",
            character_request="an original fox waving",
            original_request="make a fox",
            route="generate",
            output_root=root,
        )

    def test_generate_records_one_attempt_and_objective_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            client = MagicMock()
            client.generate.return_value = {
                "task_id": "job-1",
                "request_id": "request-1",
                "image_url": "https://example.invalid/result.png",
            }
            client.download.side_effect = lambda url, path: _opaque_png(path)
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": True, "reasons": []},
                ),
            ):
                attempt = workbuddy.generate_source(run_dir)

            self.assertEqual(attempt["number"], 1)
            self.assertEqual(attempt["status"], "awaiting_visual_decision")
            self.assertTrue((run_dir / "01_source_attempt_01.png").is_file())
            _, state = workbuddy.load_state(run_dir)
            self.assertEqual(len(state["attempts"]), 1)

            with self.assertRaisesRegex(RuntimeError, "awaiting_visual_decision"):
                workbuddy.generate_source(run_dir)

    def test_submitted_task_id_is_persisted_before_poll_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            client = MagicMock()

            def submit_then_timeout(prompt, urls, *, on_submitted):
                on_submitted("job-uncertain", "request-uncertain")
                raise TimeoutError("poll timed out")

            client.generate.side_effect = submit_then_timeout
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
            ):
                with self.assertRaises(TimeoutError):
                    workbuddy.generate_source(run_dir)

            _, state = workbuddy.load_state(run_dir)
            self.assertEqual(state["status"], "generation_unknown")
            self.assertEqual(state["attempts"][0]["task_id"], "job-uncertain")
            with self.assertRaisesRegex(RuntimeError, "generation_unknown"):
                workbuddy.generate_source(run_dir)

    def test_state_errors_redact_bearer_values_and_signed_url_queries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            client = MagicMock()
            client.generate.side_effect = workbuddy.TokenHubHTTPError(
                400,
                "Authorization: Bearer top-secret "
                "https://cos.example/object.png?sign=private-signature",
            )
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
            ):
                with self.assertRaises(workbuddy.TokenHubHTTPError):
                    workbuddy.generate_source(run_dir)

            state_text = (run_dir / workbuddy.STATE_FILENAME).read_text(encoding="utf-8")
            self.assertNotIn("top-secret", state_text)
            self.assertNotIn("private-signature", state_text)
            self.assertIn("REDACTED", state_text)

    def test_resume_generation_polls_existing_task_without_new_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            _, state = workbuddy.load_state(run_dir)
            candidate = run_dir / "01_source_attempt_01.png"
            state["attempts"].append(
                {
                    "number": 1,
                    "file": str(candidate),
                    "task_id": "job-uncertain",
                    "request_id": "request-1",
                    "status": "generation_unknown",
                    "cos_objects": [],
                    "cos_cleanup": [],
                }
            )
            state["status"] = "generation_unknown"
            workbuddy._write_json(run_dir / workbuddy.STATE_FILENAME, state)
            client = MagicMock()
            client.poll.return_value = {
                "task_id": "job-uncertain",
                "request_id": "request-1",
                "image_url": "https://example.invalid/result.png",
            }
            client.download.side_effect = lambda url, path: _opaque_png(path)
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": True, "reasons": []},
                ),
            ):
                attempt = workbuddy.resume_generation(run_dir)

            client.poll.assert_called_once_with("job-uncertain")
            self.assertEqual(attempt["status"], "awaiting_visual_decision")
            _, updated = workbuddy.load_state(run_dir)
            self.assertEqual(len(updated["attempts"]), 1)

    def test_async_download_failure_resumes_same_paid_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            first_client = MagicMock()

            def completed_after_submit(prompt, urls, *, on_submitted):
                on_submitted("job-download", "request-download")
                return {
                    "task_id": "job-download",
                    "request_id": None,
                    "image_url": "https://example.invalid/result.png",
                }

            first_client.generate.side_effect = completed_after_submit
            first_client.download.side_effect = workbuddy.TokenHubError("download failed")
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[]),
                patch.object(workbuddy, "TokenHubClient", return_value=first_client),
            ):
                with self.assertRaisesRegex(workbuddy.TokenHubError, "download failed"):
                    workbuddy.generate_source(run_dir)

            _, pending = workbuddy.load_state(run_dir)
            self.assertEqual(pending["status"], "download_pending")
            self.assertEqual(pending["attempts"][0]["task_id"], "job-download")

            resumed_client = MagicMock()
            resumed_client.poll.return_value = {
                "task_id": "job-download",
                "request_id": None,
                "image_url": "https://example.invalid/result.png",
            }
            resumed_client.download.side_effect = lambda url, path: _opaque_png(path)
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "TokenHubClient", return_value=resumed_client),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": True, "reasons": []},
                ),
            ):
                attempt = workbuddy.resume_generation(run_dir)

            resumed_client.poll.assert_called_once_with("job-download")
            self.assertEqual(attempt["status"], "awaiting_visual_decision")
            _, complete = workbuddy.load_state(run_dir)
            self.assertEqual(len(complete["attempts"]), 1)

    def test_generation_hard_stops_after_three_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            client = MagicMock()
            client.generate.side_effect = lambda prompt, urls, **kwargs: {
                "task_id": f"job-{client.generate.call_count}",
                "request_id": "request",
                "image_url": "https://example.invalid/result.png",
            }
            client.download.side_effect = lambda url, path: _opaque_png(path)
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": False, "reasons": ["bad grid"]},
                ),
            ):
                for _ in range(3):
                    workbuddy.generate_source(run_dir)
                with self.assertRaisesRegex(RuntimeError, "maximum of three"):
                    workbuddy.generate_source(run_dir)

    def test_import_workbuddy_candidate_uses_shared_attempt_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="native",
                character_request="an original pixel fox",
                original_request="make it",
                route="generate",
                output_root=tmp,
            )
            sources = []
            for number in range(1, 4):
                source = Path(tmp) / f"native-{number}.png"
                _opaque_png(source)
                sources.append(source)
            passed = {
                "passed": True,
                "fully_opaque": True,
                "pure_white_border": True,
                "detected_grid": {"width": 72, "height": 72},
                "reasons": [],
            }
            with patch.object(workbuddy, "_objective_preflight", return_value=passed):
                first = workbuddy.import_workbuddy_candidate(
                    run_dir, source_image=sources[0]
                )
                self.assertEqual(first["provider"], "workbuddy")
                self.assertEqual(first["reference_transport"], "workbuddy-native")
                workbuddy.decide_source(
                    run_dir,
                    attempt_number=1,
                    decision="rejected",
                    reason="visual mismatch",
                )
                second = workbuddy.import_workbuddy_candidate(
                    run_dir, source_image=sources[1]
                )
                self.assertEqual(second["number"], 2)
                workbuddy.decide_source(
                    run_dir,
                    attempt_number=2,
                    decision="rejected",
                    reason="visual mismatch",
                )
                workbuddy.import_workbuddy_candidate(run_dir, source_image=sources[2])
                with self.assertRaisesRegex(RuntimeError, "maximum of three"):
                    workbuddy.import_workbuddy_candidate(
                        run_dir, source_image=sources[2]
                    )

    def test_import_workbuddy_candidate_requires_decision_before_next_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="native",
                character_request="an original pixel fox",
                original_request="make it",
                route="generate",
                output_root=tmp,
            )
            source = Path(tmp) / "native.png"
            _opaque_png(source)
            passed = {
                "passed": True,
                "fully_opaque": True,
                "pure_white_border": True,
                "detected_grid": {"width": 72, "height": 72},
                "reasons": [],
            }
            with patch.object(workbuddy, "_objective_preflight", return_value=passed):
                workbuddy.import_workbuddy_candidate(run_dir, source_image=source)
                with self.assertRaisesRegex(RuntimeError, "awaiting_visual_decision"):
                    workbuddy.import_workbuddy_candidate(run_dir, source_image=source)

    def test_reference_url_rejection_falls_back_to_cos_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            reference = Path(tmp) / "reference.png"
            _opaque_png(reference)
            client = MagicMock()
            client.generate.side_effect = [
                workbuddy.TokenHubHTTPError(400, "images URL format is invalid"),
                {
                    "task_id": "job-2",
                    "request_id": "request-2",
                    "image_url": "https://example.invalid/result.png",
                },
            ]
            client.download.side_effect = lambda url, path: _opaque_png(path)
            cos = MagicMock()
            cos.uploaded_keys = ["workbuddy-reference/run/reference.png"]
            cos.upload.return_value = (
                ["https://signed.example/reference.png"],
                list(cos.uploaded_keys),
            )
            cos.cleanup.return_value = [
                {"key": cos.uploaded_keys[0], "deleted": True}
            ]
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "_cos_credentials", return_value=("id", "key")),
                patch.object(workbuddy, "prepare_references", return_value=[reference]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(workbuddy, "CosReferenceTransport", return_value=cos),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": True, "reasons": []},
                ),
            ):
                attempt = workbuddy.generate_source(run_dir)

            self.assertEqual(client.generate.call_count, 2)
            self.assertEqual(attempt["reference_transport"], "cos-signed-url")
            cos.cleanup.assert_called_once_with(cos.uploaded_keys)
            self.assertTrue(attempt["cos_cleanup"][0]["deleted"])

    def test_poll_error_after_submission_never_triggers_cos_resubmission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            reference = Path(tmp) / "reference.png"
            _opaque_png(reference)
            client = MagicMock()

            def submit_then_poll_error(prompt, urls, *, on_submitted):
                on_submitted("job-existing", "request-existing")
                raise workbuddy.TokenHubHTTPError(400, "image URL format query error")

            client.generate.side_effect = submit_then_poll_error
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "prepare_references", return_value=[reference]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(workbuddy, "_cos_credentials") as cos_credentials,
            ):
                with self.assertRaises(workbuddy.TokenHubHTTPError):
                    workbuddy.generate_source(run_dir)

            self.assertEqual(client.generate.call_count, 1)
            cos_credentials.assert_not_called()
            _, state = workbuddy.load_state(run_dir)
            self.assertEqual(state["status"], "generation_unknown")

    def test_partial_cos_upload_records_keys_for_retryable_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            reference = Path(tmp) / "reference.png"
            _opaque_png(reference)
            client = MagicMock()
            client.generate.side_effect = workbuddy.TokenHubHTTPError(
                400, "images URL format is invalid"
            )
            failed_transport = MagicMock()
            failed_transport.uploaded_keys = ["workbuddy-reference/run/first.png"]
            failed_transport.upload.side_effect = RuntimeError("second upload failed")
            failed_transport.cleanup.return_value = [
                {
                    "key": failed_transport.uploaded_keys[0],
                    "deleted": False,
                    "error": "Timeout",
                }
            ]
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "_cos_credentials", return_value=("id", "key")),
                patch.object(workbuddy, "prepare_references", return_value=[reference]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(
                    workbuddy, "CosReferenceTransport", return_value=failed_transport
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "second upload failed"):
                    workbuddy.generate_source(run_dir)

            _, state = workbuddy.load_state(run_dir)
            self.assertEqual(
                state["attempts"][0]["cos_objects"], failed_transport.uploaded_keys
            )
            self.assertTrue(state["cleanup_required"])

    def test_cos_cleanup_failure_blocks_further_work_until_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            reference = Path(tmp) / "reference.png"
            _opaque_png(reference)
            client = MagicMock()
            client.generate.side_effect = [
                workbuddy.TokenHubHTTPError(400, "images URL format is invalid"),
                {
                    "task_id": "job-2",
                    "request_id": "request-2",
                    "image_url": "https://example.invalid/result.png",
                },
            ]
            client.download.side_effect = lambda url, path: _opaque_png(path)
            cos = MagicMock()
            cos.uploaded_keys = ["workbuddy-reference/run/reference.png"]
            cos.upload.return_value = (["https://signed.example/reference.png"], cos.uploaded_keys)
            cos.cleanup.return_value = [
                {"key": cos.uploaded_keys[0], "deleted": False, "error": "Timeout"}
            ]
            with (
                patch.object(workbuddy, "_tokenhub_api_key", return_value="secret"),
                patch.object(workbuddy, "_cos_credentials", return_value=("id", "key")),
                patch.object(workbuddy, "prepare_references", return_value=[reference]),
                patch.object(workbuddy, "TokenHubClient", return_value=client),
                patch.object(workbuddy, "CosReferenceTransport", return_value=cos),
                patch.object(
                    workbuddy,
                    "_objective_preflight",
                    return_value={"passed": True, "reasons": []},
                ),
            ):
                workbuddy.generate_source(run_dir)

            _, state = workbuddy.load_state(run_dir)
            self.assertTrue(state["cleanup_required"])
            with self.assertRaisesRegex(RuntimeError, "cleanup is required"):
                workbuddy.convert_run(run_dir)

    def test_objective_preflight_enforces_opacity_border_and_density(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            with patch.object(
                workbuddy,
                "detect_source_grid",
                return_value={"width": 60, "height": 85},
            ):
                passing = workbuddy._objective_preflight(source)
            self.assertTrue(passing["passed"])

            Image.new("RGBA", (32, 32), (255, 255, 255, 128)).save(source)
            with patch.object(
                workbuddy,
                "detect_source_grid",
                return_value={"width": 59, "height": 86},
            ):
                failing = workbuddy._objective_preflight(source)
            self.assertFalse(failing["passed"])
            self.assertGreaterEqual(len(failing["reasons"]), 2)

    def test_tokenhub_client_submits_and_polls_async_job(self) -> None:
        config = json.loads(json.dumps(workbuddy.DEFAULT_CONFIG))
        config["tokenhub"]["poll_interval_seconds"] = 0
        session = _FakeSession(
            [
                _FakeResponse({"id": "job-1", "status": "queued"}),
                _FakeResponse({"id": "job-1", "status": "running"}),
                _FakeResponse(
                    {
                        "id": "job-1",
                        "request_id": "request-1",
                        "status": "completed",
                        "data": [{"url": "https://example.invalid/result.png"}],
                    }
                ),
            ]
        )
        client = workbuddy.TokenHubClient("secret", config, session=session)

        result = client.generate("prompt", [])

        self.assertEqual(result["task_id"], "job-1")
        self.assertEqual(len(session.post_calls), 3)
        submit_payload = session.post_calls[0]["json"]
        self.assertEqual(submit_payload["logo_add"], 0)
        self.assertEqual(submit_payload["model"], "hy-image-v3.0")

    def test_tokenhub_poll_accepts_completion_without_request_id(self) -> None:
        config = json.loads(json.dumps(workbuddy.DEFAULT_CONFIG))
        config["tokenhub"]["poll_interval_seconds"] = 0
        session = _FakeSession(
            [
                _FakeResponse(
                    {
                        "id": "job-1",
                        "status": "completed",
                        "data": [{"url": "https://example.invalid/result.png"}],
                    }
                )
            ]
        )
        client = workbuddy.TokenHubClient("secret", config, session=session)

        result = client.poll("job-1")

        self.assertEqual(result["task_id"], "job-1")
        self.assertIsNone(result["request_id"])

    def test_tokenhub_client_accepts_synchronous_response(self) -> None:
        config = json.loads(json.dumps(workbuddy.DEFAULT_CONFIG))
        session = _FakeSession(
            [
                _FakeResponse(
                    {
                        "request_id": "request-sync",
                        "data": [{"url": "https://example.invalid/sync.png"}],
                    }
                )
            ]
        )
        client = workbuddy.TokenHubClient("secret", config, session=session)

        result = client.generate("prompt", [])

        self.assertEqual(result["task_id"], "request-sync")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(session.post_calls), 1)

    def test_tokenhub_timeout_does_not_resubmit_job(self) -> None:
        config = json.loads(json.dumps(workbuddy.DEFAULT_CONFIG))
        config["tokenhub"]["timeout_seconds"] = -1
        session = _FakeSession([_FakeResponse({"id": "job-1", "status": "queued"})])
        client = workbuddy.TokenHubClient("secret", config, session=session)

        with self.assertRaisesRegex(TimeoutError, "did not finish"):
            client.generate("prompt", [])

        self.assertEqual(len(session.post_calls), 1)


class WorkBuddyConversionTests(unittest.TestCase):
    def test_nonbinary_alpha_requires_mask_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "partial.png"
            Image.new("RGBA", (16, 16), (20, 40, 60, 128)).save(source)
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert this",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )
            with self.assertRaisesRegex(ValueError, "non-binary alpha"):
                workbuddy.convert_run(run_dir)

    def test_direct_conversion_never_allows_ambiguous_mask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert this",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )
            with patch.object(workbuddy, "run_pipeline", return_value=run_dir) as pipeline:
                result = workbuddy.convert_run(run_dir)

            self.assertEqual(result, run_dir)
            self.assertFalse(pipeline.call_args.kwargs["allow_ambiguous_mask"])
            self.assertIsNone(pipeline.call_args.kwargs["generation_metadata"])
            provenance = pipeline.call_args.kwargs["source_provenance"]
            _, state = workbuddy.load_state(run_dir)
            self.assertEqual(provenance["original_path"], state["source_image"])
            self.assertEqual(provenance["sha256"], state["source_sha256"])

    def test_generated_conversion_passes_safe_generation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = workbuddy.init_run(
                character_name="generated",
                character_request="generated",
                original_request="make it",
                route="generate",
                output_root=Path(tmp) / "output",
            )
            candidate = run_dir / "01_source_attempt_01.png"
            _opaque_png(candidate)
            _, state = workbuddy.load_state(run_dir)
            state["attempts"].append(
                {
                    "number": 1,
                    "file": str(candidate),
                    "provider": "tokenhub",
                    "model": "hy-image-v3.0",
                    "objective_validation": {"passed": True},
                    "visual_decision": None,
                    "status": "awaiting_visual_decision",
                }
            )
            workbuddy._write_json(run_dir / workbuddy.STATE_FILENAME, state)
            workbuddy.decide_source(
                run_dir,
                attempt_number=1,
                decision="accepted",
                reason="passes",
            )

            with patch.object(workbuddy, "run_pipeline", return_value=run_dir) as pipeline:
                workbuddy.convert_run(run_dir)

            metadata = pipeline.call_args.kwargs["generation_metadata"]
            self.assertEqual(metadata["selected_attempt"], 1)
            self.assertEqual(metadata["provider"], "tokenhub")
            self.assertNotIn("api_key", json.dumps(metadata))

    def test_workbuddy_candidate_is_selected_manifest_provider(self) -> None:
        state = {
            "route": "generate",
            "attempts": [
                {
                    "number": 1,
                    "provider": "workbuddy",
                    "model": "workbuddy-default",
                    "logo_add": None,
                }
            ],
            "selected_attempt": 1,
        }

        metadata = workbuddy._generation_manifest(state)

        self.assertEqual(metadata["provider"], "workbuddy")
        self.assertEqual(metadata["model"], "workbuddy-default")
        self.assertIsNone(metadata["logo_add"])

    def test_failed_pipeline_is_archived_before_mask_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )

            def fail_pipeline(*args, **kwargs):
                (run_dir / "manifest.json").write_text(
                    json.dumps({"status": "failed"}) + "\n", encoding="utf-8"
                )
                (run_dir / "02_mask_review_overlay.png").write_bytes(b"overlay")
                raise RuntimeError("ambiguous mask")

            with patch.object(workbuddy, "run_pipeline", side_effect=fail_pipeline):
                with self.assertRaisesRegex(RuntimeError, "ambiguous mask"):
                    workbuddy.convert_run(run_dir)

            mask = Path(tmp) / "mask.png"
            Image.new("L", (32, 32), 255).save(mask)
            with patch.object(workbuddy, "run_pipeline", return_value=run_dir):
                workbuddy.convert_run(run_dir, mask_override=mask)

            archive = run_dir / "pipeline_failures" / "attempt_01"
            self.assertTrue((archive / "manifest.json").is_file())
            self.assertTrue((archive / "02_mask_review_overlay.png").is_file())

    def test_pipeline_archive_is_persisted_before_later_preflight_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )

            def fail_pipeline(*args, **kwargs):
                (run_dir / "manifest.json").write_text(
                    json.dumps({"status": "failed"}) + "\n", encoding="utf-8"
                )
                raise RuntimeError("first failure")

            with patch.object(workbuddy, "run_pipeline", side_effect=fail_pipeline):
                with self.assertRaisesRegex(RuntimeError, "first failure"):
                    workbuddy.convert_run(run_dir)

            _, state = workbuddy.load_state(run_dir)
            Path(state["source_image"]).write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "registered direct source changed"):
                workbuddy.convert_run(run_dir)

            _, persisted = workbuddy.load_state(run_dir)
            archived_manifest = Path(persisted["pipeline_attempts"][-1]["manifest"])
            self.assertIn("pipeline_failures", str(archived_manifest))
            self.assertTrue(archived_manifest.is_file())

    def test_interrupted_pipeline_is_marked_and_archived_before_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            _opaque_png(source)
            run_dir = workbuddy.init_run(
                character_name="direct",
                character_request="direct",
                original_request="convert",
                route="direct",
                output_root=Path(tmp) / "output",
                source_image=source,
            )
            _, state = workbuddy.load_state(run_dir)
            state["status"] = "converting"
            state["pipeline_attempts"].append(
                {
                    "number": 1,
                    "started_at": workbuddy._now_iso(),
                    "finished_at": None,
                    "status": "running",
                    "manifest": str(run_dir / "manifest.json"),
                }
            )
            workbuddy._write_json(run_dir / workbuddy.STATE_FILENAME, state)
            (run_dir / "manifest.json").write_text(
                json.dumps({"status": "running"}) + "\n", encoding="utf-8"
            )

            with patch.object(workbuddy, "run_pipeline", return_value=run_dir):
                workbuddy.convert_run(run_dir)

            _, completed = workbuddy.load_state(run_dir)
            interrupted = completed["pipeline_attempts"][0]
            self.assertEqual(interrupted["status"], "interrupted")
            self.assertIsNotNone(interrupted["finished_at"])
            self.assertTrue(Path(interrupted["manifest"]).is_file())


if __name__ == "__main__":
    unittest.main()
