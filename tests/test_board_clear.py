#!/usr/bin/env python3
"""
Board-clear (collection-detector) tests.

The detect loop's `all_done` branch must return to `watching` once the player
COLLECTS the darts. An ABSOLUTE empty-fg threshold is permanently defeated when a
grazing camera outlines the board's spider wires as a few-thousand-px phantom
foreground after a board/camera shift: the empty board then reads ABOVE the
threshold and the loop sticks in `all_done` forever (every later visit ignored).

The fix detects the collection's RELATIVE signature instead — an arm spike
(max_fg far above the darts-in level, and/or a contour storm) followed by fg
settling BELOW the darts-in level. These tests:

  * replay the recorded fg sequence from match_20260614_110606 through both the
    OLD (absolute) and the NEW (collection) rules and assert the OLD rule NEVER
    clears across the stuck window while the NEW rule clears shortly after each
    collection (t≈30 and t≈47), and
  * cover synthetic spike-then-drop (= collected → clear) and spike-then-RISE
    (= a dart was ADDED, not removed → NOT clear) cases.

Run: python3 test_board_clear.py
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import json
from pathlib import Path

import detect


REC = Path("debug_recordings/match_20260614_110606")


# ── the rules under test (mirrors detect.py's all_done branch) ──────────────────

class CollectionClear:
    """The NEW collection-based clear logic, as a standalone state object so a
    recorded fg sequence can be driven through it frame by frame. Mirrors the
    `all_done` branch of detect._run_detection (constants pulled from detect)."""

    def __init__(self):
        self.fg_darts_in = 0
        self.arm_spiked  = False

    def step(self, max_fg, scene_settled, storm):
        # Measure darts-in on the first settled all_done frame.
        if scene_settled and self.fg_darts_in == 0 and max_fg > detect.EMPTY_FG:
            self.fg_darts_in = max_fg
        if self.fg_darts_in and (
                max_fg > self.fg_darts_in * detect.COLLECT_SPIKE_FACTOR
                or storm > detect.MAX_SCORE_CONTOURS):
            self.arm_spiked = True
        drop_target = int(self.fg_darts_in * detect.COLLECT_DROP_FRACTION)
        return (
            (self.arm_spiked and scene_settled and max_fg < drop_target)
            or max_fg < detect.EMPTY_FG)


def old_clear(max_fg, fg_darts_in):
    """The OLD absolute-threshold rule (the regression)."""
    clear_thresh = max(detect.EMPTY_FG, int(fg_darts_in * detect.CLEAR_FRACTION))
    return max_fg < clear_thresh


# ── recorded fg sequence ────────────────────────────────────────────────────────

def load_alldone_fg(rec):
    """Ordered (t, max_fg, settled, storm) for the all_done phase of the recording.
    `storm` = max contour count any camera shows (cam_darts), the contour-storm
    half of the arm-spike test."""
    rows = []
    for line in (rec / "telemetry.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e.get("kind") != "fg" or e.get("phase") != "all_done":
            continue
        cam = e.get("cam_darts") or {}
        storm = max((v for v in cam.values()), default=0)
        rows.append((e["t"], int(e["max_fg"]), bool(e.get("settled")), storm))
    rows.sort()
    return rows


# ── tests ───────────────────────────────────────────────────────────────────────

def test_recorded_collection():
    rows = load_alldone_fg(REC)
    assert rows, "no all_done fg events in recording"

    # fg_darts_in is measured on the first settled all_done frame (~t21.9 → 6784).
    fg_darts_in = next(fg for _t, fg, settled, _s in rows
                       if settled and fg > detect.EMPTY_FG)
    assert fg_darts_in == 6784, f"darts-in baseline drifted: {fg_darts_in}"

    new = CollectionClear()
    new_clear_times = []
    old_clear_times = []
    for t, fg, settled, storm in rows:
        if new.step(fg, settled, storm):
            new_clear_times.append(t)
        if old_clear(fg, fg_darts_in):
            old_clear_times.append(t)

    # OLD rule: never clears anywhere in the stuck window — the regression.
    assert not old_clear_times, (
        f"OLD absolute rule unexpectedly cleared at {old_clear_times} "
        f"(thresh={max(detect.EMPTY_FG, int(fg_darts_in*detect.CLEAR_FRACTION))})")

    # NEW rule: clears shortly after the 1st collection (spike t30.18, settles
    # ~3786 at t32+) and again after the 2nd (spike t47.59, settles ~3783 at t49+).
    assert any(31 < t < 37 for t in new_clear_times), (
        f"NEW rule did not clear after 1st collection (~t32); got {new_clear_times}")
    assert any(48 < t < 56 for t in new_clear_times), (
        f"NEW rule did not clear after 2nd collection (~t49); got {new_clear_times}")
    print(f"  recorded: OLD never clears (thresh="
          f"{max(detect.EMPTY_FG, int(fg_darts_in*detect.CLEAR_FRACTION))}); "
          f"NEW clears at t="
          f"{[round(t,1) for t in new_clear_times[:1]]}... and t="
          f"{[round(t,1) for t in new_clear_times if t > 40][:1]}")


def test_synthetic_spike_then_drop():
    """Arm spikes, then board settles BELOW darts-in → collected → clear."""
    new = CollectionClear()
    seq = [  # (max_fg, settled, storm)
        (6784, True, 3),    # darts in, baseline
        (6800, True, 3),
        (54985, False, 6),  # arm reaches in (spike)
        (3786, True, 2),    # settles low — darts gone
    ]
    results = [new.step(*s) for s in seq]
    assert results == [False, False, False, True], results
    print("  synthetic spike-then-drop: clears on the low settle  OK")


def test_synthetic_spike_then_rise():
    """Arm spikes, then board settles ABOVE darts-in (a dart was ADDED, not
    removed) → NOT a collection → must NOT clear."""
    new = CollectionClear()
    seq = [
        (6784, True, 3),    # darts in
        (40000, False, 5),  # arm reaches in (spike)
        (9000, True, 3),    # settles HIGHER than darts-in — extra dart, not empty
    ]
    results = [new.step(*s) for s in seq]
    assert results == [False, False, False], results
    print("  synthetic spike-then-rise: stays NOT clear (dart added)  OK")


def test_storm_counts_as_spike():
    """A contour storm (arm shatters into many blobs) arms the spike even if
    max_fg never crosses the factor."""
    new = CollectionClear()
    new.step(6784, True, 3)            # baseline
    new.step(7000, True, 20)           # contour storm (no big fg jump) → arm_spiked
    assert new.arm_spiked, "contour storm did not arm the spike"
    assert new.step(3000, True, 2), "did not clear after storm + low settle"
    print("  contour storm arms the spike  OK")


if __name__ == "__main__":
    tests = [
        test_recorded_collection,
        test_synthetic_spike_then_drop,
        test_synthetic_spike_then_rise,
        test_storm_counts_as_spike,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(tests)} board-clear tests passed.")
