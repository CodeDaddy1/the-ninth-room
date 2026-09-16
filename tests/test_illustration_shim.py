# -*- coding: utf-8 -*-
"""The propose session's `higgsfield` cannot spend, upload or train.

A dispatched session runs with permissions skipped; detection after the
fact is not a gate. The shim at pipeline/bridge/higgsfield_readonly/ is
first on that session's PATH, forwards the read-only verbs to the real
CLI and refuses the rest before any network call. This file runs the shim
as a subprocess, the way the session would, against a fake "real" binary
that records what reached it.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHIM = Path(__file__).resolve().parents[1] / "pipeline" / "bridge" / "higgsfield_readonly" / "higgsfield"


class Shim(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.real = self.tmp / "real"
        self.real.write_text("#!/bin/sh\necho REAL $@\n")
        self.real.chmod(0o755)
        self.log = self.tmp / "shim.log"
        (self.tmp / "family.jpg").write_bytes(b"x")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_shim(self, *args):
        env = dict(os.environ, NINTH_ROOM_HIGGSFIELD_REAL=str(self.real),
                   NINTH_ROOM_HIGGSFIELD_SHIM_LOG=str(self.log))
        p = subprocess.run([sys.executable, str(SHIM), *args], capture_output=True,
                           text=True, env=env, cwd=str(self.tmp))
        return p.returncode, p.stdout, p.stderr

    def test_it_is_executable_and_uses_the_system_python(self):
        self.assertTrue(os.access(SHIM, os.X_OK))
        self.assertTrue(SHIM.read_text().startswith("#!/usr/bin/python3"))

    def test_read_only_verbs_reach_the_real_binary(self):
        for args in (["account", "status"], ["model", "list"], ["version"],
                     ["generate", "cost", "kling3_0", "--prompt", "x",
                      "--start-image", "67837121-457c-42eb-ba69-53b9272b865b"],
                     ["generate", "get", "67837121-457c-42eb-ba69-53b9272b865b"]):
            rc, out, err = self.run_shim(*args)
            self.assertEqual(rc, 0, (args, err))
            self.assertIn("REAL " + " ".join(args), out)

    def test_create_workflow_upload_and_soul_are_refused_before_the_network(self):
        for args in (["generate", "create", "kling3_0", "--prompt", "x"],
                     ["workflow", "list"], ["upload", "x.png"],
                     ["soul-id", "create", "--name", "Caleb"],
                     ["marketing-studio", "run"]):
            rc, out, err = self.run_shim(*args)
            self.assertEqual(rc, 2, args)
            self.assertNotIn("REAL", out)
            self.assertIn("refused", err)

    def test_a_local_path_on_any_flag_is_refused(self):
        rc, out, err = self.run_shim("generate", "cost", "nano_banana_pro", "--prompt", "x",
                                     "--image", str(self.tmp / "family.jpg"))
        self.assertEqual(rc, 2)
        self.assertIn("local path", err)
        rc, out, err = self.run_shim("generate", "cost", "nano_banana_pro", "--prompt", "x",
                                     "--image", "family.jpg")
        self.assertEqual(rc, 2, "a relative path is still a path")

    def test_every_call_lands_in_the_log(self):
        self.run_shim("account", "status")
        self.run_shim("generate", "create", "x")
        lines = self.log.read_text().splitlines()
        self.assertTrue(lines[0].startswith("forwarded\t"))
        self.assertTrue(lines[1].startswith("refused\t"))


if __name__ == "__main__":
    unittest.main()
