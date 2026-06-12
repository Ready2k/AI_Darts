"""
Checkout (finishing) suggestions for X01 games.

Given a remaining score and how many darts are left in the visit, find a
sequence of throws that finishes the leg. With double-out (the default), the
final dart must be a double or the inner bull (D-Bull = 50).

The solver is preference-ordered so the first solution it returns is the one a
player would actually throw: set up with the biggest trebles, finish on a
common double.
"""

# Finishing darts that legally close a double-out leg: value -> label.
DOUBLES = {2 * s: f"D{s}" for s in range(1, 21)}
DOUBLES[50] = "DBull"

# Every dart you might throw to *set up* a finish, in rough preference order:
# big trebles first, then the bull, then singles high→low, then doubles.
_SETUP = (
    [(3 * s, f"T{s}") for s in range(20, 0, -1)]
    + [(50, "DBull"), (25, "Bull")]
    + [(s, f"{s}") for s in range(20, 0, -1)]
    + [(2 * s, f"D{s}") for s in range(20, 0, -1)]
)

# Any single dart (used for straight-out / non-double finishes).
_ANY_SINGLE = {}
for _s in range(1, 21):
    _ANY_SINGLE.setdefault(_s, f"{_s}")
    _ANY_SINGLE.setdefault(2 * _s, f"D{_s}")
    _ANY_SINGLE.setdefault(3 * _s, f"T{_s}")
_ANY_SINGLE.setdefault(25, "Bull")
_ANY_SINGLE.setdefault(50, "DBull")

# Smallest possible finish per number of remaining darts, used to prune.
_MIN_FINISH = 2  # cheapest double is D1 = 2


def _solve(score, darts, double_out):
    """Return a list of throw labels finishing `score` in exactly `darts`, or None."""
    if darts == 1:
        if double_out:
            return [DOUBLES[score]] if score in DOUBLES else None
        return [_ANY_SINGLE[score]] if score in _ANY_SINGLE else None

    for value, label in _SETUP:
        rest = score - value
        # Leave at least enough for the remaining darts to finish on a double.
        if rest < (_MIN_FINISH if double_out else 1):
            continue
        tail = _solve(rest, darts - 1, double_out)
        if tail is not None:
            return [label] + tail
    return None


def suggest(score, darts_left=3, double_out=True):
    """
    Best finishing path for `score` using up to `darts_left` darts.

    Returns a list of throw labels (e.g. ["T20", "T20", "DBull"]) or None if the
    score cannot be checked out with the darts available.
    """
    if score <= 1 and double_out:
        return None
    if score <= 0:
        return None
    for n in range(1, darts_left + 1):
        path = _solve(score, n, double_out)
        if path is not None:
            return path
    return None


def is_checkout(score, darts_left=3, double_out=True):
    """True if `score` can be finished with the darts available."""
    return suggest(score, darts_left, double_out) is not None
