#!/usr/bin/env python3
"""Tests for the Autodarts adapter against the REAL local board-manager schema
(captured live from board manager v1.0.7 via ws://localhost:3180/api/events).

Run:  python3 test_autodarts_adapter.py
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from game import X01Game
import autodarts_adapter as ad

_p = _f = 0


def check(name, got, want):
    global _p, _f
    if got == want:
        _p += 1
        print(f"  OK  {name}")
    else:
        _f += 1
        print(f"FAIL  {name}\n        got : {got}\n        want: {want}")


def lab(h):
    return None if h is None else (h.label, h.points, h.ring, h.multiplier)


# ── notation → Hit ────────────────────────────────────────────────────────────
check("T20", lab(ad.notation_to_hit("T20")), ("Triple 20", 60, "TRIPLE", 3))
check("D12", lab(ad.notation_to_hit("d12")), ("Double 12", 24, "DOUBLE", 2))
check("S5", lab(ad.notation_to_hit("S5")), ("5", 5, "SINGLE", 1))
check("BULL", lab(ad.notation_to_hit("BULL")), ("Bullseye", 50, "INNER_BULL", 1))
check("OUTER", lab(ad.notation_to_hit("OUTER")), ("Bull", 25, "OUTER_BULL", 1))
check("MISS", lab(ad.notation_to_hit("MISS")), ("Miss", 0, "MISS", 1))
check("M5 (board miss)", lab(ad.notation_to_hit("M5")), ("Miss", 0, "MISS", 1))
check("M20 (board miss)", lab(ad.notation_to_hit("m20")), ("Miss", 0, "MISS", 1))
check("garbage -> None", ad.notation_to_hit("ZZ"), None)

# confidence float → level (used when an engine like OpenDartboard supplies it)
check("0.95 confirmed", ad.confidence_level(0.95), "confirmed")
check("0.75 provisional", ad.confidence_level(0.75), "provisional")
check("None confirmed", ad.confidence_level(None), "confirmed")

# ── throw → Hit + board-mm position (coords are normalized, y-up, 1.0≈double ring)
hit, pos = ad.throw_to_hit({"segment": {"name": "S20", "number": 20,
                                        "bed": "SingleOuter", "multiplier": 1},
                            "coords": {"x": 0.0517, "y": 0.8814}})
check("throw_to_hit S20", lab(hit), ("20", 20, "SINGLE", 1))
check("coords scaled to mm (y up toward 20)", (round(pos[0], 1), round(pos[1], 1)),
      (round(0.0517 * 170, 1), round(0.8814 * 170, 1)))

# ── the REAL captured visit: S20, S18, S7 = 45, then takeout ───────────────────
# (verbatim from ws://localhost:3180/api/events; throws[] is cumulative per visit)
def state(event, status, throws):
    return {"type": "state",
            "data": {"connected": True, "running": True, "status": status,
                     "event": event, "numThrows": len(throws), "throws": throws}}

T20 = {"segment": {"name": "S20", "number": 20, "bed": "SingleOuter", "multiplier": 1},
       "coords": {"x": 0.0517, "y": 0.8814}}
T18 = {"segment": {"name": "S18", "number": 18, "bed": "SingleOuter", "multiplier": 1},
       "coords": {"x": 0.4442, "y": 0.5649}}
T7 = {"segment": {"name": "S7", "number": 7, "bed": "SingleInner", "multiplier": 1},
      "coords": {"x": -0.3200, "y": -0.3360}}

g = X01Game(["A"], start_score=501)
c = ad.AutodartsConsumer()
c.on_message(state("Throw detected", "Throw", [T20]), g)
check("after dart 1: 481", g.players[0].score, 481)
# cumulative re-send of the same throw must NOT double-count
c.on_message(state("Throw detected", "Throw", [T20]), g)
check("re-sent throws[] does not double-count", g.players[0].score, 481)
c.on_message(state("Throw detected", "Throw", [T20, T18]), g)
c.on_message(state("Throw detected", "Takeout", [T20, T18, T7]), g)
check("visit scored 45 (501-45=456)", g.players[0].score, 456)
check("three darts recorded", len(g._last_visit_turn) + len(g.turn), 3)
check("dart confidence = confirmed", g.to_dict()["display_turn"][0]["confidence"],
      "confirmed")

# ── short visit + takeout advances (trusted engine, no prompt) ─────────────────
g2 = X01Game(["A", "B"], start_score=501)
c2 = ad.AutodartsConsumer()
c2.on_message(state("Throw detected", "Throw", [T20, T18]), g2)   # only 2 darts
check("mid short visit: still A", g2.current, 0)
c2.on_message(state("Takeout started", "Takeout in progress", [T20, T18]), g2)
check("takeout on short visit advances to B", g2.current, 1)
check("A kept its 38 (501-38=463)", g2.players[0].score, 463)
# next visit (numThrows rolls back) records cleanly, no leftover double-count
c2.on_message(state("Throw detected", "Throw", [T7]), g2)
check("next visit records for B", g2.players[1].score, 494)

# Manual reset clears the per-visit counter
g3 = X01Game(["A"])
c3 = ad.AutodartsConsumer()
c3.on_message(state("Throw detected", "Throw", [T20]), g3)
c3.on_message(state("Manual reset", "Throw", []), g3)
c3.on_message(state("Throw detected", "Throw", [T18]), g3)
check("after manual reset, a fresh S18 records", g3.to_dict()["turn"][-1]["label"], "18")

# ── reconciliation: visit closes early but Autodarts keeps reporting ───────────
# BUST on dart 1: Autodarts still reports darts 2 & 3 of that visit — they must be
# ignored, not leak onto the next player. (NB: T20/T18/T7 above are the captured
# SINGLES; use a real triple here.)
REAL_T20 = {"segment": {"name": "T20", "number": 20, "bed": "Triple", "multiplier": 3},
            "coords": {"x": 0.0, "y": 0.6}}
gb = X01Game(["A", "B"], start_score=50)   # A on 50; T20 (60) busts
cb = ad.AutodartsConsumer()
cb.on_message(state("Throw detected", "Throw", [REAL_T20]), gb)        # bust -> advance to B
check("bust advances to B", gb.current, 1)
check("A reverted to 50 after bust", gb.players[0].score, 50)
cb.on_message(state("Throw detected", "Throw", [REAL_T20, T18]), gb)   # stray dart 2
cb.on_message(state("Throw detected", "Takeout", [REAL_T20, T18, T7]), gb)  # stray dart 3
check("stray post-bust darts ignored (still B's turn, no darts)",
      (gb.current, len(gb.turn)), (1, 0))
check("B untouched by stray darts", gb.players[1].score, 50)
cb.on_message(state("Takeout started", "Takeout in progress", [REAL_T20, T18, T7]), gb)
check("no double-advance on takeout after bust", gb.current, 1)

# CHECKOUT on dart 1: match over; remaining reported darts ignored, no error.
D20 = {"segment": {"name": "D20", "number": 20, "bed": "Double", "multiplier": 2},
       "coords": {"x": 0.0, "y": 0.95}}
gc = X01Game(["A"], start_score=40)
cc = ad.AutodartsConsumer()
cc.on_message(state("Throw detected", "Throw", [D20]), gc)          # 40 - D20 = win
check("checkout wins the match", gc.over and gc.winner.name == "A", True)
check("score 0 on checkout", gc.players[0].score, 0)
cc.on_message(state("Throw detected", "Throw", [D20, T20]), gc)     # stray darts after win
cc.on_message(state("Takeout started", "Takeout in progress", [D20, T20]), gc)
check("match stays won, score unchanged after stray darts",
      (gc.over, gc.players[0].score), (True, 0))

# ── full scripted game via the mock's real-schema messages → our engine ────────
import mock_autodarts
g4 = X01Game(["A"], start_score=501)
c4 = ad.AutodartsConsumer()
for m in mock_autodarts.game_messages():
    c4.on_message(m, g4)
check("mock 501 game checks out (D12) -> over", g4.over, True)
check("winner is A", g4.winner.name if g4.winner else None, "A")
check("final score 0", g4.players[0].score, 0)


if __name__ == "__main__":
    print(f"\n{_p} passed, {_f} failed")
    sys.exit(1 if _f else 0)
