"""Unit tests for the shaft-line-intersection tip finder (line_tips.py).

Geometry only: homographies are identity (pixel == canonical) so the tests exercise
the line-fitting / intersection / multi-camera-concurrence logic directly. Real
optical validation (flight-end rejection on actual footage) is done by replay
against recorded matches, not here.
"""

import math
from line_tips import find_tips_by_lines

I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]   # identity homography
_fails = 0


def check(cond, msg):
    global _fails
    print(f"  {'OK ' if cond else 'FAIL'} {msg}")
    if not cond:
        _fails += 1


def shaft(tip, d, length=80):
    """A shaft segment with its TIP at `tip`, extending toward the flight along d
    (so the board-contact tip is an endpoint, as in reality)."""
    n = math.hypot(*d)
    ux, uy = d[0] / n, d[1] / n
    return (tip, (tip[0] + ux * length, tip[1] + uy * length))


def nearest(tips, P):
    return min(tips, key=lambda t: math.hypot(t[0][0] - P[0], t[0][1] - P[1]))


print("three concurrent shaft lines → one tip")
tip = (200, 150)
shafts = {
    0: [shaft(tip, (1, 2))],
    1: [shaft(tip, (1, -1))],
    2: [shaft(tip, (0, 1))],
}
tips = find_tips_by_lines(shafts, {0: I, 1: I, 2: I}, min_cams=2)
check(len(tips) == 1, f"exactly one tip (got {len(tips)})")
if tips:
    t = nearest(tips, tip)
    check(math.hypot(t[0][0] - tip[0], t[0][1] - tip[1]) < 1.0, "tip at the true intersection")
    check(len(t[1]) == 3, f"all 3 cameras support it (got {len(t[1])})")

print("two darts → two tips")
A, B = (200, 150), (300, 300)
shafts = {
    0: [shaft(A, (1, 2)), shaft(B, (2, 1))],
    1: [shaft(A, (1, -1)), shaft(B, (1, -2))],
    2: [shaft(A, (0, 1)), shaft(B, (1, 1))],
}
tips = find_tips_by_lines(shafts, {0: I, 1: I, 2: I}, min_cams=2)
check(len(tips) == 2, f"two distinct tips (got {len(tips)})")
check(math.hypot(nearest(tips, A)[0][0] - A[0], nearest(tips, A)[0][1] - A[1]) < 1.5, "dart A localised")
check(math.hypot(nearest(tips, B)[0][0] - B[0], nearest(tips, B)[0][1] - B[1]) < 1.5, "dart B localised")

print("spurious 2-camera crossing rejected at min_cams=3")
# cam0 and cam1 lines cross at (200,150); cam2 has a line nowhere near it.
shafts = {
    0: [shaft((200, 150), (1, 0))],
    1: [shaft((200, 150), (0, 1))],
    2: [shaft((20, 480), (1, 0))],
}
tips3 = find_tips_by_lines(shafts, {0: I, 1: I, 2: I}, min_cams=3)
check(len(tips3) == 0, f"no 3-camera tip from a 2-camera crossing (got {len(tips3)})")
tips2 = find_tips_by_lines(shafts, {0: I, 1: I, 2: I}, min_cams=2)
check(any(math.hypot(t[0][0] - 200, t[0][1] - 150) < 1.0 for t in tips2),
      "but the tight 2-camera crossing is found at min_cams=2")

print("a single camera cannot make a tip")
tips = find_tips_by_lines({0: [shaft((200, 150), (1, 1))]}, {0: I}, min_cams=2)
check(len(tips) == 0, f"one camera → no tip (got {len(tips)})")

print("off-plane flight divergence does not pull the tip")
# All three cameras agree on the tip line; each also has a *flight* line that only
# its own camera sees diverging away — must not corrupt the tip or invent a tip.
tip = (250, 120)
shafts = {
    0: [shaft(tip, (1, 3)), shaft((400, 400), (1, 0))],
    1: [shaft(tip, (-1, 3)), shaft((60, 420), (0, 1))],
    2: [shaft(tip, (0, 1)), shaft((430, 300), (1, 1))],
}
tips = find_tips_by_lines(shafts, {0: I, 1: I, 2: I}, min_cams=3)
check(any(math.hypot(t[0][0] - tip[0], t[0][1] - tip[1]) < 1.5 and len(t[1]) == 3 for t in tips),
      "true tip recovered with 3-camera support despite per-camera flight lines")

print()
if _fails:
    print(f"{_fails} failed")
    raise SystemExit(1)
print("all passed")
