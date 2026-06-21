#!/usr/bin/env python3
"""Regression tests for the state-machine replay (replay_state.StateReplay).

These pin the headline detection outcomes the offline state machine must keep
producing on real recordings, so a future change to detect.step_tracker /
line_tips that breaks them fails here instead of in a live match. Windows are
kept SMALL (a couple of seconds of footage) so the suite stays fast.

    python3 test_replay_state.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from replay_state import StateReplay

REC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug_recordings")

_passed = 0
_failed = 0


def check(name, got, want):
    global _passed, _failed
    if got == want:
        print(f"  OK  {name}")
        _passed += 1
    else:
        print(f"FAIL  {name}\n        got : {got}\n        want: {want}")
        _failed += 1


def labels(scored):
    return [d["label"] for d in scored]


def test_134104_ghost_suppressed():
    """134104 (threw 8 then 11): the current geometry must score 8,11 with NO
    ghost 8 — the recording's own telemetry has the buggy 8,11,8."""
    sr = StateReplay(os.path.join(REC, "match_20260614_134104"))
    sr.run()
    check("134104 scores 8,11 with no ghost", labels(sr.scored), ["8", "11"])
    sr.close()


def test_135743_visit1():
    """135743 visit 1 must resolve 19, 7, 8 and complete the visit (all_done)."""
    sr = StateReplay(os.path.join(REC, "match_20260614_135743"))
    sr.run(1, 230)
    check("135743 visit 1 = 19,7,8", labels(sr.scored), ["19", "7", "8"])
    check("135743 visit 1 completes (-> all_done)",
          [t["to"] for t in sr.transitions], ["all_done"])
    sr.close()


def test_135743_visit4_touching_darts():
    """135743 visit 4 is TWO darts touching in segment 14 (~8px apart). The 2nd
    one fuses with the first in cam0 and lands inside the scored-dedup radius.

    DEFAULT (ARRIVAL_DEDUP_BYPASS off): the 2nd dart is dropped as a duplicate, so
    only one 14 scores — the conservative behaviour while reliability work refocuses
    on detection. With the bypass enabled, both 14s are recovered (capability intact)."""
    import detect
    assert detect.ARRIVAL_DEDUP_BYPASS is False, "bypass must default OFF"
    sr = StateReplay(os.path.join(REC, "match_20260614_135743"))
    sr.run(900, 1100)
    check("135743 visit 4 default: one 14 (2nd dropped as dup)",
          labels(sr.scored), ["14"])
    sr.close()

    detect.ARRIVAL_DEDUP_BYPASS = True
    try:
        sr = StateReplay(os.path.join(REC, "match_20260614_135743"))
        sr.run(900, 1100)
        check("135743 visit 4 with bypass ON: both touching 14s recovered",
              labels(sr.scored), ["14", "14"])
        sr.close()
    finally:
        detect.ARRIVAL_DEDUP_BYPASS = False


def test_135743_no_visit_over_three():
    """Safety invariant: never double-count a single dart. Across the whole
    recording (default behaviour), no visit may exceed 3 scored darts."""
    sr = StateReplay(os.path.join(REC, "match_20260614_135743"))
    sr.run()
    # split the scored stream into visits at each all_done transition
    alldone_times = [t["t"] for t in sr.transitions if t["to"] == "all_done"]
    bounds = alldone_times + [1e9]
    per_visit, vi = [0] * (len(bounds)), 0
    for d in sr.scored:
        while d["t"] > bounds[vi]:
            vi += 1
        per_visit[vi] += 1
    check("135743 total darts == 10 (default, bypass off)", len(sr.scored), 10)
    check("135743 no visit exceeds 3 darts", max(per_visit) <= 3, True)
    sr.close()


def test_confidence_model():
    """Confidence is camera-count based, never spread (a 2-line intersection is
    always spread 0)."""
    import detect
    check("3 cams -> confirmed", detect.dart_confidence(3)[0], detect.CONF_CONFIRMED)
    check("2 cams -> provisional", detect.dart_confidence(2)[0], detect.CONF_PROVISIONAL)
    check("1 cam -> low", detect.dart_confidence(1)[0], detect.CONF_LOW)


def test_scored_events_carry_confidence_and_audit():
    """Every scored dart emits a confidence + a per-camera detection audit."""
    sr = StateReplay(os.path.join(REC, "match_20260614_134104"))
    sr.run()
    scored = [e for e in sr.events if e["kind"] == "scored"]
    audits = [e for e in sr.events if e["kind"] == "dart_audit"]
    check("every scored dart has a confidence", all("confidence" in e for e in scored),
          True)
    check("a dart_audit is emitted per scored dart", len(audits), len(scored))
    if audits:
        cams = audits[0]["cameras"]
        ok = all({"seen", "candidates", "fg_area", "contour_areas"} <= set(v.keys())
                 for v in cams.values())
        check("audit records per-camera seen/candidates/fg/contours", ok, True)


if __name__ == "__main__":
    test_134104_ghost_suppressed()
    test_135743_visit1()
    test_135743_visit4_touching_darts()
    test_135743_no_visit_over_three()
    test_confidence_model()
    test_scored_events_carry_confidence_and_audit()
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)
