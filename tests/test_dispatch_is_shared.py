# -*- coding: utf-8 -*-
"""A job may not launch its own Claude session.

Seven sites in jobs.py launched the CLI by absolute path. Two were the
shared helpers; the other five — fixer, research, scout, publish, sourcing
— were whole copies of `_dispatch` that had drifted only in whether their
error message used an em dash or two hyphens (2026-08-28).

Why it matters beyond tidiness: the job contract puts staging-and-promote
inside the dispatch helper, so a runner that launches its own session
silently opts out of the guarantee that a malformed artifact never lands.
Two of the five accounted for three of the five "session finished but
nothing was written" failures in the frozen baseline.

This is a ratchet, not a style rule. It only falls.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import ast
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JOBS_PY = Path(__file__).resolve().parent.parent / "pipeline" / "jobs.py"

# The only two functions entitled to start a session.
DISPATCHERS = {"_dispatch", "_dispatch_json"}


def _functions():
    tree = ast.parse(JOBS_PY.read_text())
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


class DispatchIsShared(unittest.TestCase):

    def test_only_the_helpers_name_the_binary(self):
        offenders = []
        for fn in _functions():
            if fn.name in DISPATCHERS:
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Name) and node.id == "CLAUDE_BIN":
                    offenders.append(fn.name)
        self.assertEqual(sorted(set(offenders)), [],
                         "these launch their own session — call _dispatch "
                         "or _dispatch_json instead")

    def test_the_path_itself_appears_exactly_once(self):
        """Hardcoded in seven places before. One constant now."""
        self.assertEqual(JOBS_PY.read_text().count('"~'), 1)

    def test_the_helpers_are_still_called(self):
        """A guard that passes because nothing dispatches any more would
        be worthless."""
        called = set()
        for fn in _functions():
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in DISPATCHERS):
                    called.add(node.func.id)
        self.assertEqual(called, DISPATCHERS)

    def test_the_five_that_were_collapsed_still_dispatch(self):
        """Named so a regression points at the incident, not at a count."""
        want = {"_run_fixer", "_run_research", "_run_scout",
                "_run_publish", "_run_sourcing"}
        found = set()
        for fn in _functions():
            if fn.name not in want:
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in DISPATCHERS):
                    found.add(fn.name)
        self.assertEqual(found, want)


if __name__ == "__main__":
    unittest.main()
