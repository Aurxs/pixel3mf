from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import build_workbuddy_skill as builder  # noqa: E402


class WorkBuddySkillBuildTests(unittest.TestCase):
    def test_checked_in_skill_matches_canonical_source_and_overlay(self) -> None:
        self.assertTrue(builder.skill_tree_matches())

    def test_host_prompt_is_packaged_without_changing_codex_template(self) -> None:
        host = (builder.TARGET_DIR / "references/generation-prompt.md").read_text()
        core = (builder.SOURCE_DIR / "references/generation-prompt.md").read_text()
        self.assertEqual(host, builder.GENERATION_PROMPT_PATH.read_text())
        self.assertIn("64 × 64", host)
        self.assertIn("24 × 24 pixel-art design as the visual prior", core)

    def test_host_acceptance_matches_import_candidate_lifecycle(self) -> None:
        acceptance = (builder.TARGET_DIR / "references/source-acceptance.md").read_text()
        skill = (builder.TARGET_DIR / "SKILL.md").read_text()
        self.assertIn("01_source_attempt_NN.png", acceptance)
        self.assertIn("background_normalization", acceptance)
        self.assertNotIn("prompt's `24 × 24` language", acceptance)
        self.assertIn("decide --decision accepted", skill)
        self.assertNotIn("After `01_source.png` exists", skill)

    def test_workbuddy_validator_accepts_generated_skill(self) -> None:
        builder.validate_skill()

    def test_package_is_deterministic_and_has_one_top_level_skill(self) -> None:
        first = builder.package_skill()
        first_digest = hashlib.sha256(first.read_bytes()).hexdigest()
        second = builder.package_skill()
        second_digest = hashlib.sha256(second.read_bytes()).hexdigest()
        self.assertEqual(first_digest, second_digest)
        with zipfile.ZipFile(second) as archive:
            names = archive.namelist()
        self.assertIn("pixel-art-to-3mf/SKILL.md", names)
        self.assertTrue(all(name.startswith("pixel-art-to-3mf/") for name in names))


if __name__ == "__main__":
    unittest.main()
