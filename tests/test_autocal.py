"""Synthetic test for ellipse-based auto-calibration. Run: python3 test_autocal.py"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import math
import cv2
import numpy as np

import auto_calibrate as ac

passed = failed = 0
def check(name, cond):
    global passed, failed
    passed, failed = passed + bool(cond), failed + (not cond)
    print(f"  {'OK' if cond else 'XX'}  {name}")


# Build a board (light disc) and project it to an oblique (perspective) view.
img = np.full((720, 1280, 3), 25, np.uint8)
cv2.circle(img, (360, 360), 250, (210, 205, 195), -1)
cv2.circle(img, (360, 360), 250, (255, 255, 255), 4)
src = np.float32([[110, 110], [610, 110], [610, 610], [110, 610]])
dst = np.float32([[300, 160], [980, 120], [1040, 640], [260, 600]])
H = cv2.getPerspectiveTransform(src, dst)
warp = cv2.warpPerspective(img, H, (1280, 720))

ell = ac.detect_board_ellipse(cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY))
check("ellipse detected", ell is not None)

(cx, cy), (MA, ma), _ = ell
true_c = cv2.perspectiveTransform(np.float32([[[360, 360]]]), H).reshape(2)
check("centre near true board centre", math.hypot(cx - true_c[0], cy - true_c[1]) < 60)
check("fit is elliptical under perspective", max(MA, ma) / min(MA, ma) > 1.1)

h = ac.ellipse_to_handles(ell)
check("four handles returned", h.shape == (4, 2))
ys, xs = h[:, 1], h[:, 0]
check("handle[0] is topmost", h[0][1] == ys.min())
check("handle[2] is bottom-most", h[2][1] == ys.max())
check("handle[1] is rightmost", h[1][0] == xs.max())
check("handle[3] is leftmost", h[3][0] == xs.min())

# Frontal (circular) board → Hough/ellipse fallback still yields handles.
h2 = ac.auto_handles(img)
check("frontal board yields handles", h2 is not None and h2.shape == (4, 2))

# Empty frame → no detection (graceful None).
check("blank frame returns None", ac.auto_handles(np.full((720, 1280, 3), 25, np.uint8)) is None)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
