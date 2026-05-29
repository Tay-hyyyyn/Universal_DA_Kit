from __future__ import annotations

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
            "docs/agent/measurement-log.md",
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


if __name__ == "__main__":
    unittest.main()
