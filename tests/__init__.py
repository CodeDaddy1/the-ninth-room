# Engine tests. Run: /usr/bin/python3 -m unittest discover -s tests -t .

# No test may spawn a real Claude session.
#
# 2026-08-25, twice in one day:
#   * the creative jobs moved from `_dispatch` to `_dispatch_json` to
#     capture their session id, and one guard test still stubbed the OLD
#     name — so the suite dispatched real sessions. 250 seconds instead of
#     2, real spend, and enough machine load that unrelated local-lane jobs
#     timed out and reported as failures.
#   * then a sourcing test stubbed `_dispatch` while `_run_sourcing` calls
#     subprocess.Popen directly, so it slipped past the first version of
#     this guard and spawned another one.
#
# Stubbing the named helpers was therefore the wrong altitude: five jobs
# still build their own Popen, and any new one might. The refusal now sits
# on the single thing every dispatch site has in common — launching the
# claude binary — so a stale stub fails loudly and instantly instead of
# quietly costing money.
#
# Set NINTH_ALLOW_SESSIONS=1 to opt a run back in.
import os
import subprocess

if os.environ.get("NINTH_ALLOW_SESSIONS") != "1":
    _REAL_POPEN = subprocess.Popen

    def _is_claude(args):
        try:
            first = args[0] if isinstance(args, (list, tuple)) else args
        except (IndexError, TypeError):
            return False
        return isinstance(first, str) and first.rstrip("/").endswith("claude")

    class _NoSessions(_REAL_POPEN):
        def __init__(self, args, *a, **kw):
            if _is_claude(args):
                raise AssertionError(
                    "a test tried to spawn a real Claude session — stub the "
                    "dispatcher the job actually calls, or set "
                    "NINTH_ALLOW_SESSIONS=1 if a live session is intended")
            super().__init__(args, *a, **kw)

    subprocess.Popen = _NoSessions
