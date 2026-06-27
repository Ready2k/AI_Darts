"""Single-elimination tournament ("cups") layered over the shared game engine.

A bracket of 2-8 players is persisted to tournament.json. Each tie is played as
a normal match via detect.new_game(); when a match finishes the server's
game-over watcher calls record_result(winner) to advance the bracket, and the
next tie is started on demand (POST /api/tournament/next). Byes are auto-won.
"""

import json
import random
import threading
from pathlib import Path

STATE_FILE = Path("tournament.json")
_LOCK = threading.RLock()
_T = None   # in-memory current tournament dict, or None


def _name(p):
    return (p["name"] if isinstance(p, dict) else str(p)) if p is not None else None


def _save():
    try:
        if _T is None:
            STATE_FILE.unlink(missing_ok=True)
        else:
            STATE_FILE.write_text(json.dumps(_T, indent=2))
    except OSError:
        pass


def load():
    """Restore a persisted tournament on startup (best-effort)."""
    global _T
    if STATE_FILE.exists():
        try:
            _T = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            _T = None
    return _T


def _pair(entries):
    """Pair a list of entries into matches (last one gets a bye if odd)."""
    matches = []
    for i in range(0, len(entries), 2):
        a = entries[i]
        b = entries[i + 1] if i + 1 < len(entries) else None
        matches.append({"a": a, "b": b, "winner": _name(a) if b is None else None})
    return matches


def _resolve_byes():
    rnd = _T["rounds"][_T["cur_round"]]
    for m in rnd:
        if m["winner"] is None and m["b"] is None and m["a"] is not None:
            m["winner"] = _name(m["a"])


def _round_complete(rnd):
    return all(m["winner"] is not None for m in rnd)


def _advance_if_round_done():
    """If the current round is fully decided, build the next round (or crown)."""
    _resolve_byes()
    rnd = _T["rounds"][_T["cur_round"]]
    if not _round_complete(rnd):
        return
    winners = [m["winner"] for m in rnd]
    if len(winners) == 1:
        _T["champion"] = winners[0]
        _T["status"] = "done"
        return
    by_name = {_name(e): e for e in _T["players"]}
    wentries = [by_name.get(w, {"name": w}) for w in winners]
    _T["rounds"].append(_pair(wentries))
    _T["cur_round"] += 1
    _advance_if_round_done()   # a bye-only next round resolves immediately


def create(players, mode=None, config=None, shuffle=True):
    """Build a bracket. `players`: list of {name,is_ai,ai_level} or names."""
    global _T
    entries = [p if isinstance(p, dict) else {"name": str(p)}
               for p in (players or []) if _name(p) and _name(p).strip()]
    if len(entries) < 2:
        return None
    if shuffle:
        random.shuffle(entries)
    with _LOCK:
        _T = {
            "mode": mode or "501",
            "config": config or {},
            "players": entries,
            "rounds": [_pair(entries)],
            "cur_round": 0,
            "champion": None,
            "status": "active",
        }
        _advance_if_round_done()
        _save()
    return _T


def current_match():
    """The next tie to play (both opponents real), or None if done/awaiting."""
    with _LOCK:
        if _T is None or _T["status"] != "active":
            return None
        _advance_if_round_done()
        if _T["status"] != "active":
            return None
        rnd = _T["rounds"][_T["cur_round"]]
        for mi, m in enumerate(rnd):
            if m["winner"] is None and m["a"] is not None and m["b"] is not None:
                return {"round": _T["cur_round"], "match": mi, "a": m["a"], "b": m["b"]}
        return None


def record_result(winner_name):
    """Record the winner of the in-progress tie and advance the bracket."""
    with _LOCK:
        cm = current_match()
        if cm is None:
            return None
        m = _T["rounds"][cm["round"]][cm["match"]]
        valid = {_name(m["a"]), _name(m["b"])}
        m["winner"] = winner_name if winner_name in valid else _name(m["a"])
        _advance_if_round_done()
        _save()
        return _T


def state():
    return _T


def clear():
    global _T
    with _LOCK:
        _T = None
        _save()
