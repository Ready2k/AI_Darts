#!/usr/bin/env python3
"""
Auto-calibration helper for the alignment step.

A dartboard viewed off-axis projects to an *ellipse*, not a circle. This module
fits that ellipse and converts it into four perspective-correct diamond handles
(top / right / bottom / left) so the user starts from a board-shaped overlay
instead of a flat circle — then only needs to rotate it so the numbers line up.

Why not fully automatic? The ellipse pins down the board's position, size and
perspective, but not its *rotation* (which wedge is "20") — that needs the
segment colours/wires and a real camera to tune. So this is a strong starting
point, not a one-click finish.
"""

import math

import cv2
import numpy as np


def detect_board_ellipse(gray, debug=False):
    """
    Fit an ellipse to the dartboard boundary.

    Returns an OpenCV ellipse ((cx, cy), (major, minor), angle_deg) or None.
    Strategy: edge map → contours → keep the largest contour whose fitted
    ellipse is board-sized and reasonably filled; fall back to HoughCircles.
    """
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (7, 7), 1.5)

    min_r = min(h, w) * 0.20
    max_r = min(h, w) * 0.70
    min_area = math.pi * min_r * min_r

    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best, best_area = None, 0.0
    for c in contours:
        if len(c) < 5:
            continue
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        (cx, cy), (MA, ma), angle = cv2.fitEllipse(c)
        major, minor = max(MA, ma), min(MA, ma)
        if minor <= 0:
            continue
        ell_r = major / 2
        if not (min_r <= ell_r <= max_r):
            continue
        if minor / major < 0.45:          # too squashed to be a board boundary
            continue
        ell_area = math.pi * (MA / 2) * (ma / 2)
        fill = area / ell_area if ell_area else 0
        if fill < 0.55:                   # contour doesn't really trace the ellipse
            continue
        if ell_area > best_area:
            best_area = ell_area
            best = ((cx, cy), (MA, ma), angle)

    if best is not None:
        if debug:
            print(f"    ellipse fit: centre ({best[0][0]:.0f},{best[0][1]:.0f}) "
                  f"axes ({best[1][0]:.0f},{best[1][1]:.0f}) angle {best[2]:.0f}")
        return best

    # Fallback: HoughCircles → degenerate (circular) ellipse
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=min(h, w) // 2,
        param1=80, param2=40, minRadius=int(min_r), maxRadius=int(max_r))
    if circles is not None:
        cx, cy, rad = circles[0][0]
        if debug:
            print(f"    hough fallback: centre ({cx:.0f},{cy:.0f}) r {rad:.0f}")
        return ((float(cx), float(cy)), (float(2 * rad), float(2 * rad)), 0.0)

    if debug:
        print("    no board ellipse found")
    return None


def ellipse_to_handles(ellipse):
    """
    Convert a fitted ellipse into 4 diamond handles on its boundary, ordered
    [top, right, bottom, left] by screen position (matching the canonical
    Seg 20 / 6 / 3 / 11 control points). Returns a float32 (4, 2) array.

    The four points are the ellipse's axis endpoints — four points 90° apart on
    the board — which give a perspective-correct (rotation-aside) starting fit.
    """
    (cx, cy), (MA, ma), angle = ellipse
    a, b = MA / 2, ma / 2
    th = math.radians(angle)
    cos_t, sin_t = math.cos(th), math.sin(th)

    pts = []
    for t in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        ex, ey = a * math.cos(t), b * math.sin(t)          # ellipse-local
        x = cx + ex * cos_t - ey * sin_t                   # rotate to image
        y = cy + ex * sin_t + ey * cos_t
        pts.append((x, y))

    # Sort clockwise (0 = up), then rotate the list so the topmost point is
    # first → [top, right, bottom, left].
    pts.sort(key=lambda p: math.atan2(p[0] - cx, -(p[1] - cy)) % (2 * math.pi))
    top = min(range(4), key=lambda i: pts[i][1])
    pts = pts[top:] + pts[:top]
    return np.array(pts, dtype=np.float32)


def auto_handles(frame, debug=False):
    """Detect the board in a BGR frame and return 4 handles, or None."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ellipse = detect_board_ellipse(gray, debug=debug)
    if ellipse is None:
        return None
    return ellipse_to_handles(ellipse)
