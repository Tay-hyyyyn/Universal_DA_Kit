from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicPackageTest(unittest.TestCase):
    def test_expected_package_files_exist(self) -> None:
        expected = [
            "README.md",
            "pyproject.toml",
            "Manual/AGENTS.md",
            "Manual/CLAUDE.md",
            "Manual/config/new_dataset_config.example.json",
            "Manual/config/analysis_config.template.json",
            "Manual/plugins/_shared/manual_common.py",
            "Manual/run_manual_pipeline.ps1",
            "docs/agent/context-packet.md",
            "docs/agent/learned-notes.md",
            "docs/agent/measurement-log.md",
            "docs/agent/workflow-recipes.md",
            "examples/generic_regression_sample.csv",
        ]
        for relative in expected:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).exists())

    def test_public_text_does_not_expose_private_paths(self) -> None:
        banned = [
            "C:" + "\\Users",
            "wl" + "xog",
            "Served" + " Data",
        ]
        suffixes = {".md", ".py", ".ps1", ".json", ".toml", ".csv", ".txt"}
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or path.suffix.lower() not in suffixes:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in banned:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_agent_guides_are_paired_and_identical(self) -> None:
        for agents_path in ROOT.rglob("AGENTS.md"):
            claude_path = agents_path.with_name("CLAUDE.md")
            with self.subTest(directory=agents_path.parent.relative_to(ROOT)):
                self.assertTrue(claude_path.exists())
                self.assertEqual(agents_path.read_bytes(), claude_path.read_bytes())

    def test_manifest_references_existing_docs_and_stage_files(self) -> None:
        manifest_path = ROOT / "Manual" / "agent_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for relative in manifest["primary_docs"]:
            with self.subTest(kind="primary_doc", relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        for stage in manifest["stages"]:
            for key in ("skill", "script"):
                relative = stage[key]
                with self.subTest(kind=key, stage=stage["id"], relative=relative):
                    self.assertTrue((ROOT / relative).is_file())

    def test_docs_have_no_retired_harness_references(self) -> None:
        retired = [
            "AGENT_USAGE_GUIDELINES.md",
            "MANUAL_PLUGIN_AND_REPORT_REVIEW.md",
            "$agent-verify",
            "Desktop\\Must Read It",
        ]
        paths = [ROOT / "README.md", ROOT / "WORKFLOW_USER_MANUAL.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md"]
        for directory in (ROOT / "Manual", ROOT / "docs"):
            paths.extend(path for path in directory.rglob("*") if path.is_file())
        for path in paths:
            if path.suffix.lower() not in {".md", ".json", ".toml", ".ps1", ".py", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in retired:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_pre_commit_is_self_contained(self) -> None:
        hook = ROOT / ".githooks" / "pre-commit"
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            (temp_root / "AGENTS.md").write_text("same\n", encoding="utf-8")
            (temp_root / "CLAUDE.md").write_text("same\n", encoding="utf-8")
            passed = subprocess.run(
                [sys.executable, str(hook)],
                cwd=temp_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)

            (temp_root / "CLAUDE.md").write_text("different\n", encoding="utf-8")
            failed = subprocess.run(
                [sys.executable, str(hook)],
                cwd=temp_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("Agent guide check failed", failed.stderr)

    def test_user_manual_shows_required_pipeline_arguments(self) -> None:
        text = (ROOT / "WORKFLOW_USER_MANUAL.md").read_text(encoding="utf-8")
        self.assertIn("-Config Manual\\config\\<project_config>.json", text)
        self.assertIn("-RunId <run_id>", text)


if __name__ == "__main__":
    unittest.main()
