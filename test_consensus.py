"""Tests for multi-dart cross-camera consensus clustering (detect.find_consensus_tips).

Run: python3 test_consensus.py
"""
import numpy as np

import detect

I = np.eye(3, dtype=np.float64)
H = {0: I, 1: I, 2: I}   # identity homographies → canonical == pixel coords

_passed = _failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  OK  {name}")
    else:
        _failed += 1
        print(f"FAIL  {name}")


def positions(clusters):
    return sorted([pos for pos, *_ in clusters], key=lambda p: p[0])


# Two darts, all three cameras see both tips, plus a scattered flight end each.
tips = {
    0: [((101, 100), 50), ((299, 301), 50), (( 40, 420), 20)],
    1: [(( 99, 101), 50), ((301, 300), 50), ((430,  60), 20)],
    2: [((100,  99), 50), ((300, 299), 50), ((250, 470), 15)],
}
c = detect.find_consensus_tips(tips, H, min_cams=2)
check("two darts → two clusters", len(c) == 2)
check("each dart has 3-camera agreement", all(len(cams) == 3 for _, cams, _ in c))
check("real-tip clusters are tight", all(spread < 5 for _, _, spread in c))
ps = positions(c)
check("dart A near (100,100)", abs(ps[0][0] - 100) < 5 and abs(ps[0][1] - 100) < 5)
check("dart B near (300,300)", abs(ps[1][0] - 300) < 5 and abs(ps[1][1] - 300) < 5)

# Single dart with one flight-end outlier per camera.
tips1 = {
    0: [((200, 200), 50), (( 33, 400), 15)],
    1: [((202, 199), 50), ((410,  90), 15)],
    2: [((199, 201), 50), (( 90, 330), 15)],
}
c1 = detect.find_consensus_tips(tips1, H, min_cams=2)
check("single dart → one cluster", len(c1) == 1 and len(c1[0][1]) == 3)

# A lone tip seen by only one camera must not survive the 2-camera filter.
tips_lone = {0: [((123, 321), 50)], 1: [], 2: []}
check("single-camera blip rejected at min_cams=2",
      detect.find_consensus_tips(tips_lone, H, min_cams=2) == [])
check("single-camera blip kept at min_cams=1",
      len(detect.find_consensus_tips(tips_lone, H, min_cams=1)) == 1)

# Three tightly-grouped darts (e.g. three in T20) still separate into three.
tips3 = {
    0: [((250,  80), 50), ((262,  84), 50), ((256,  96), 50)],
    1: [((251,  81), 50), ((263,  83), 50), ((257,  97), 50)],
    2: [((249,  79), 50), ((261,  85), 50), ((255,  95), 50)],
}
c3 = detect.find_consensus_tips(tips3, H, min_cams=2)
check("three grouped darts → three clusters", len(c3) == 3)
check("grouped darts each 3-cam", all(len(cams) == 3 for _, cams, _ in c3))

# A loose multi-camera cluster (flight-end coincidence): points associate (within
# CANONICAL_CLUSTER of the seed) but don't agree tightly, so spread > CLUSTER_TIGHT
# and the tracker rejects it.
tips_loose = {0: [((200, 200), 30)], 1: [((250, 200), 30)], 2: [((200, 250), 30)]}
cl = detect.find_consensus_tips(tips_loose, H, min_cams=2)
check("loose coincidental cluster has large spread",
      len(cl) == 1 and cl[0][2] > detect.CLUSTER_TIGHT)

print(f"\n{_passed} passed, {_failed} failed")
raise SystemExit(1 if _failed else 0)
