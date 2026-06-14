"""Shaft-line-intersection dart tip finder.

The robust way to localise a dart tip across cameras (James's insight, 2026-06):
a dart is a rigid rod, so in each camera it is a straight LINE. Fit that line,
warp the whole line into canonical board space through the plane homography, and
— because a homography maps lines to lines and maps the on-board tip pixel to its
true canonical position — **every camera's warped shaft line passes through the
true tip P**, while diverging elsewhere (the flight end is ~10cm off the plane and
warps differently per camera). So the common intersection of the warped shaft
lines IS the tip. No endpoint picking, no "which end is the tip", no flight-end
phantoms: the board-plane intersection hands you the tip.

This replaces the previous approach (project BOTH endpoints and greedily cluster
them with a loose radius), which mistook a flight end for a tip and scored a 5 as
an 18 when one camera dropped the dart. Fitting a line over the whole shaft is far
less noisy than a single contour endpoint, and the intersection is well-conditioned
because the cameras view the board from different angles.

Pure geometry, no OpenCV — unit-tested in test_line_tips.py and validated against
recorded matches via replay.
"""

import math


def _warp(p, H):
    """Apply a 3x3 homography (list-of-lists or np array) to a 2D point."""
    x, y = p[0], p[1]
    w = H[2][0] * x + H[2][1] * y + H[2][2]
    if abs(w) < 1e-12:
        return None
    return ((H[0][0] * x + H[0][1] * y + H[0][2]) / w,
            (H[1][0] * x + H[1][1] * y + H[1][2]) / w)


def _line_point_dist(P, a, b):
    """Perpendicular distance from point P to the infinite line through a, b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return math.hypot(P[0] - a[0], P[1] - a[1])
    # |cross((b-a), (P-a))| / |b-a|
    return abs(dx * (P[1] - a[1]) - dy * (P[0] - a[0])) / L


def _intersect(a1, a2, b1, b2):
    """Intersection point of line(a1,a2) and line(b1,b2); None if ~parallel."""
    d1x, d1y = a2[0] - a1[0], a2[1] - a1[1]
    d2x, d2y = b2[0] - b1[0], b2[1] - b1[1]
    den = d1x * d2y - d1y * d2x
    if abs(den) < 1e-9:
        return None
    t = ((b1[0] - a1[0]) * d2y - (b1[1] - a1[1]) * d2x) / den
    return (a1[0] + t * d1x, a1[1] + t * d1y)


def _least_squares_point(lines):
    """Point minimising the sum of squared perpendicular distances to `lines`
    (each a canonical (a, b) pair). Solves (Σ nnᵀ)P = Σ n(n·a) for unit normals n."""
    sxx = sxy = syy = bx = by = 0.0
    for a, b in lines:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        nx, ny = -dy / L, dx / L           # unit normal to the line
        c = nx * a[0] + ny * a[1]          # n · a
        sxx += nx * nx; sxy += nx * ny; syy += ny * ny
        bx += nx * c;   by += ny * c
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:                     # all lines parallel — undefined
        return None
    return ((syy * bx - sxy * by) / det,
            (sxx * by - sxy * bx) / det)


def find_tips_by_lines(shafts_by_cam, homographies, min_cams=2,
                       assoc=24.0, endcap=30.0, tight_2cam=24.0, tight_3cam=40.0,
                       board_radius=240.0, dedup=14.0, shadow=35.0, full_cams=3):
    """Localise dart tips as the concurrence of warped shaft lines.

    shafts_by_cam : {cam_idx: [(p1, p2), ...]} shaft endpoints in *pixel* space.
    homographies  : {cam_idx: 3x3} camera→canonical plane homography.

    Returns [(tip_canonical, cam_set, residual), ...], strongest (most cameras,
    then tightest) first. `residual` is the max supporting-camera line distance —
    the analogue of cluster spread, used by the caller as a confidence gate.

    A candidate is a point where ≥`min_cams` cameras each have a shaft whose line
    passes within `assoc` px AND whose nearer endpoint is within `endcap` px (the
    tip sits at the board-contact END of the shaft, so a true tip is at an endpoint
    of every contributing shaft — not merely on the infinite line, where two
    extended shafts would always cross). The point is refined by least-squares over
    the supporting lines and kept only if its residual is within the (camera-count
    dependent) tight limit. Spurious crossings of two different darts' shafts fall
    far from either shaft's ends and are rejected; the real tip — where every
    camera's shaft genuinely ends and concurs — passes.
    """
    # Warp every shaft to a canonical line, tagged with its camera.
    clines = []   # (cam, A, B)
    for cam, shafts in shafts_by_cam.items():
        H = homographies.get(cam)
        if H is None:
            continue
        for p1, p2 in shafts:
            A = _warp(p1, H)
            B = _warp(p2, H)
            if A is None or B is None:
                continue
            if math.hypot(B[0] - A[0], B[1] - A[1]) < 1e-6:
                continue
            clines.append((cam, A, B))

    # Seed candidate tips from every cross-camera pairwise intersection.
    seeds = []
    for i in range(len(clines)):
        for j in range(i + 1, len(clines)):
            if clines[i][0] == clines[j][0]:
                continue
            P = _intersect(clines[i][1], clines[i][2], clines[j][1], clines[j][2])
            if P is None:
                continue
            if math.hypot(P[0] - 250, P[1] - 250) > board_radius:
                continue
            seeds.append(P)

    # For each seed, gather the nearest supporting line per camera, refine, gate.
    tips = []
    for P in seeds:
        support = {}   # cam -> (dist, (A,B))
        for cam, A, B in clines:
            d = _line_point_dist(P, A, B)
            if d > assoc:
                continue
            dend = min(math.hypot(P[0] - A[0], P[1] - A[1]),
                       math.hypot(P[0] - B[0], P[1] - B[1]))
            if dend > endcap:                  # crossing is not near a shaft END
                continue
            if cam not in support or d < support[cam][0]:
                support[cam] = (d, (A, B))
        if len(support) < min_cams:
            continue
        refined = _least_squares_point([ab for _, ab in support.values()])
        if refined is None:
            continue
        residual = max(_line_point_dist(refined, A, B) for _, (A, B) in support.values())
        limit = tight_3cam if len(support) >= 3 else tight_2cam
        if residual > limit:
            continue
        tips.append((refined, set(support.keys()), residual))

    # Dedup: collapse tips that refined to (nearly) the same point, keeping the
    # one with the most cameras / tightest residual.
    tips.sort(key=lambda t: (-len(t[1]), t[2]))
    kept = []
    for tip, cams, res in tips:
        if any(math.hypot(tip[0] - k[0][0], tip[1] - k[0][1]) < dedup for k in kept):
            continue
        kept.append((tip, cams, res))

    # Shadow suppression: a tip with fewer than full_cams cameras sitting within
    # `shadow` px of a FULL-agreement (>= full_cams) tip is that solid dart's own
    # mis-triangulation ghost — two cameras' shafts cross a second time a few px
    # off the true tip, which all cameras actually concur on. (A real separate
    # dart that close has its own independent shafts and normally earns full
    # agreement too, so it isn't dropped.) Two cameras always intersect exactly
    # (residual 0), so without this a 2-camera ghost is geometrically
    # indistinguishable from a real tip — only its proximity to the strong tip
    # betrays it.
    strong = [k for k in kept if len(k[1]) >= full_cams]
    if strong:
        kept = [(tip, cams, res) for tip, cams, res in kept
                if len(cams) >= full_cams
                or not any(math.hypot(tip[0] - s[0][0], tip[1] - s[0][1]) <= shadow
                           for s in strong)]
    return kept
