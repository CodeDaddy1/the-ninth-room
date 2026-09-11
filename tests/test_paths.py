"""pipeline/paths.py: machine paths come from config, never from source."""
import os
import unittest
from pathlib import Path

from pipeline import paths

PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"


class PathsTest(unittest.TestCase):
    def test_env_override_wins(self):
        old = os.environ.get("NINTH_ROOM_CLAUDE_BIN")
        os.environ["NINTH_ROOM_CLAUDE_BIN"] = "/tmp/claude-test-binary"
        try:
            self.assertEqual(paths.claude_bin(), "/tmp/claude-test-binary")
        finally:
            if old is None:
                del os.environ["NINTH_ROOM_CLAUDE_BIN"]
            else:
                os.environ["NINTH_ROOM_CLAUDE_BIN"] = old

    def test_work_dir_defaults_under_the_repo(self):
        old = os.environ.pop("WORK_DIR", None)
        try:
            if not (paths.PROJECT_ROOT / ".env").exists():
                self.assertEqual(paths.work_dir(), paths.PROJECT_ROOT / "work")
            else:
                self.assertTrue(paths.work_dir().is_absolute())
        finally:
            if old is not None:
                os.environ["WORK_DIR"] = old

    def test_no_home_directory_in_pipeline_source(self):
        """A home path in source means the pipeline runs on exactly one
        laptop and a public reader cannot run it at all."""
        offenders = [p.name for p in PIPELINE.glob("*.py") if "/Users/" in p.read_text()]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
