"""Dartboard geometry and scoring."""

import math
from collections import namedtuple

# Clockwise from 12 o'clock (top = 20 segment)
SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

# Standard BDO/PDC radii in mm
BULL_R       =   6.35
BULLS_R      =  15.9
TREBLE_IN    =  99.0
TREBLE_OUT   = 107.0
DOUBLE_IN    = 162.0
DOUBLE_OUT   = 170.0   # also used as the pixel-to-mm scale reference

# A hit describes everything callers need to score *and* reason about a dart:
#   points     — value awarded (e.g. 60 for a treble 20)
#   label      — human/announcer string (e.g. "Triple 20")
#   ring       — one of: INNER_BULL, OUTER_BULL, DOUBLE, TRIPLE, SINGLE, MISS
#   segment    — the wedge number 1..20, or 25 for either bull, 0 for a miss
#   multiplier — 1/2/3 (bull counts as 1; INNER_BULL is treated as a double for
#                checkout purposes via `is_double`, not via this field)
Hit = namedtuple("Hit", ["points", "label", "ring", "segment", "multiplier"])

# Rings that legally finish a double-out leg (inner bull counts as D-Bull).
DOUBLE_OUT_RINGS = frozenset({"DOUBLE", "INNER_BULL"})


def is_double(hit):
    """True if this hit may legally start (double-in) or finish (double-out) a leg."""
    return hit.ring in DOUBLE_OUT_RINGS


def is_triple(hit):
    """True if this hit is a treble."""
    return hit.ring == "TRIPLE"


def is_master(hit):
    """True if this hit may open/finish a master-in/master-out leg (double or treble)."""
    return is_double(hit) or is_triple(hit)


def score_detail(x_mm, y_mm):
    """
    Score a dart at (x_mm, y_mm) relative to bull centre and return a full Hit.
    x positive = right, y positive = up (toward 20 segment).
    """
    r = math.sqrt(x_mm**2 + y_mm**2)

    if r <= BULL_R:
        return Hit(50, "Bullseye", "INNER_BULL", 25, 1)
    if r <= BULLS_R:
        return Hit(25, "Bull", "OUTER_BULL", 25, 1)
    if r > DOUBLE_OUT:
        return Hit(0, "Miss", "MISS", 0, 1)

    # 0° = up (20), clockwise positive
    angle = math.degrees(math.atan2(x_mm, y_mm)) % 360
    seg_idx = int((angle + 9) % 360 / 18) % 20
    seg = SEGMENTS[seg_idx]

    if r >= DOUBLE_IN:
        return Hit(seg * 2, f"Double {seg}", "DOUBLE", seg, 2)
    if TREBLE_IN <= r <= TREBLE_OUT:
        return Hit(seg * 3, f"Triple {seg}", "TRIPLE", seg, 3)
    return Hit(seg, str(seg), "SINGLE", seg, 1)


def score_at(x_mm, y_mm):
    """
    Backward-compatible scoring: returns (points, label).
    See score_detail() for the full Hit when ring/segment info is needed.
    """
    h = score_detail(x_mm, y_mm)
    return h.points, h.label
