# Engine tests. Run: /usr/bin/python3 -m unittest discover -s tests -t .

# No test may spawn a real Claude session.
#
# 2026-08-25: the creative jobs moved from `_dispatch` to `_dispatch_json`
# to capture their session id. One guard test still stubbed the OLD name,
# so the stub stopped intercepting and the suite dispatched real sessions —
# 250 seconds instead of 2, real spend, and enough machine load that
# unrelated local-lane jobs timed out and reported as failures.
#
# A stale stub is easy to write and invisible when it happens, so the
# refusal lives here rather than in each test's setUp: any dispatcher that
# is reached without being patched raises immediately and names itself.
# Set NINTH_ALLOW_SESSIONS=1 to opt a run back in.
import os

if os.environ.get("NINTH_ALLOW_SESSIONS") != "1":
    from pipeline import jobs as _jobs

    def _refuse(*_a, **_k):
        raise AssertionError(
            "a test reached the real session dispatcher — stub the "
            "dispatcher the job actually calls, or set "
            "NINTH_ALLOW_SESSIONS=1 if a live session is genuinely intended")

    _jobs._dispatch = _refuse
    _jobs._dispatch_json = _refuse
