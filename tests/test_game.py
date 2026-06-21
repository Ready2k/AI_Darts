"""Tests for the X01 game engine, checkout solver, and dartboard hit detail.

Run:  python3 test_game.py
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import dartboard
import checkout
from game import X01Game


passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# ── dartboard hit detail ────────────────────────────────────────────────────

print("dartboard.score_detail")
h = dartboard.score_detail(0, 165)
check("D20 ring/segment/mult", h.ring == "DOUBLE" and h.segment == 20 and h.multiplier == 2)
check("D20 is_double", dartboard.is_double(h))
check("inner bull is_double", dartboard.is_double(dartboard.score_detail(0, 0)))
check("outer bull not double", not dartboard.is_double(dartboard.score_detail(0, 10)))
check("T20 not double", not dartboard.is_double(dartboard.score_detail(0, 103)))
check("score_at still (pts,label)", dartboard.score_at(0, 103) == (60, "Triple 20"))


# ── checkout solver ─────────────────────────────────────────────────────────

print("checkout.suggest")
check("170 = T20 T20 DBull", checkout.suggest(170) == ["T20", "T20", "DBull"])
check("167 finishes in 3", len(checkout.suggest(167)) == 3 and checkout.suggest(167)[-1].startswith("D"))
check("40 = D20", checkout.suggest(40) == ["D20"])
check("2 = D1", checkout.suggest(2) == ["D1"])
check("1 not checkoutable (double out)", checkout.suggest(1) is None)
check("169 impossible", checkout.suggest(169) is None)
check("50 = DBull", checkout.suggest(50) == ["DBull"])
check("3 = 1,D1", checkout.suggest(3) == ["1", "D1"])
check("every double-out finish ends on a double",
      all(checkout.suggest(s)[-1].startswith("D") for s in range(2, 171)
          if checkout.suggest(s)))
check("100 finishes in 2", len(checkout.suggest(100)) == 2)
check("straight-out 1 = '1'", checkout.suggest(1, double_out=False) == ["1"])


# ── X01: basic scoring & 3-dart turns ───────────────────────────────────────

print("X01 basic flow")
g = X01Game(["A", "B"], start_score=501)
g.record_score(60, "TRIPLE", 20, 3, "T20")
g.record_score(60, "TRIPLE", 20, 3, "T20")
g.record_score(60, "TRIPLE", 20, 3, "T20")
check("A at 321 after 180", g.players[0].score == 321)
check("turn passed to B", g.current == 1)
check("A 3-dart avg = 180", abs(g.players[0].three_dart_avg - 180.0) < 1e-9)


# ── X01: bust reverts the visit ─────────────────────────────────────────────

print("X01 bust")
g = X01Game(["A"], start_score=60, double_out=True)
g.record_score(40, "DOUBLE", 20, 2, "D20")   # -> 20
ev = g.record_score(25, "OUTER_BULL", 25, 1, "Bull")  # 20-25 = -5 bust
check("bust flagged", ev["bust"] is True)
check("score reverted to 60", g.players[0].score == 60)
check("busted visit scores 0 avg", g.players[0].total_points == 0)


# ── X01: double-out rules ───────────────────────────────────────────────────

print("X01 double-out")
g = X01Game(["A"], start_score=40)
ev = g.record_score(20, "SINGLE", 20, 1, "20")        # 40->20, single, fine
check("single 20 ok", ev["bust"] is False and g.players[0].score == 20)
g2 = X01Game(["A"], start_score=20)
ev = g2.record_score(20, "SINGLE", 20, 1, "20")        # would hit 0 on a single -> bust
check("finishing on single busts", ev["bust"] is True and g2.players[0].score == 20)
g3 = X01Game(["A"], start_score=40)
ev = g3.record_score(40, "DOUBLE", 20, 2, "D20")       # 40 -> 0 on a double -> win
check("finish on double wins leg", ev["leg_won"] and ev["match_won"])
check("winner set", g3.over and g3.winner.name == "A")
g4 = X01Game(["A"], start_score=3)
ev = g4.record_score(2, "DOUBLE", 1, 2, "D1")          # 3-2=1 -> bust (can't leave 1)
check("leaving 1 busts", ev["bust"] is True)


# ── X01: double-in ──────────────────────────────────────────────────────────

print("X01 double-in")
g = X01Game(["A"], start_score=101, double_in=True, double_out=True)
g.record_score(20, "SINGLE", 20, 1, "20")   # doesn't open, no score
check("no score before opening double", g.players[0].score == 101)
check("player not opened", g.players[0].opened is False)
g.record_score(40, "DOUBLE", 20, 2, "D20")  # opens + scores
check("opens on double and scores", g.players[0].opened and g.players[0].score == 61)


# ── X01: legs / sets ────────────────────────────────────────────────────────

print("X01 legs and sets")
g = X01Game(["A", "B"], start_score=40, legs_to_win=2, sets_to_win=1)
g.record_score(40, "DOUBLE", 20, 2, "D20")   # A wins leg 1
check("A has 1 leg", g.players[0].legs == 1 and not g.over)
check("scores reset after leg", g.players[0].score == 40 and g.players[1].score == 40)
check("B starts next leg", g.current == 1)
g.record_score(40, "DOUBLE", 20, 2, "D20")   # B wins leg 1 (legs 1-1)
g.record_score(40, "DOUBLE", 20, 2, "D20")   # A starts, A wins leg -> 2 legs -> set -> match
check("A wins match", g.over and g.winner.name == "A")


# ── X01: undo ───────────────────────────────────────────────────────────────

print("X01 undo")
g = X01Game(["A", "B"], start_score=501)
g.record_score(60, "TRIPLE", 20, 3, "T20")
g.record_score(60, "TRIPLE", 20, 3, "T20")
check("at 381", g.players[0].score == 381)
g.undo()
check("undo restores 441", g.players[0].score == 441)
g.undo()
check("undo restores 501", g.players[0].score == 501)
check("undo on empty returns False", g.undo() is False)


# ── X01: positions & click-to-correct ───────────────────────────────────────

print("X01 positions and correction")
g = X01Game(["A", "B"], start_score=501)
g.record_score(60, "TRIPLE", 20, 3, "T20", position=(0.0, 103.0))
d = g.to_dict()
check("position carried into to_dict", d["turn"][0]["pos"] == [0.0, 103.0])
# Misread: scored T20 but it was really a single 20 — correct it.
ev = g.correct_last(dartboard.score_detail(0, 130))  # single 20 region
check("correct_last returns event", ev is not None)
check("score recomputed after correction", g.players[0].score == 481)
check("turn now shows corrected dart", g.to_dict()["turn"][0]["label"] == "20")
check("still A's turn (1 dart)", g.current == 0 and len(g.turn) == 1)
# Correcting can also fix a wrong bust.
g2 = X01Game(["A"], start_score=20)
ev = g2.record_score(20, "SINGLE", 20, 1, "20")        # busts (single can't finish)
check("misread single busts", ev["bust"])
g2.correct_last(dartboard.Hit(20, "D10", "DOUBLE", 10, 2))  # really was D10 -> wins
check("correction turns bust into win", g2.over and g2.winner.name == "A")
check("correct_last on empty game returns None", X01Game(["A"]).correct_last(dartboard.score_detail(0, 0)) is None)


# ── confidence + visit review (missing dart) ──────────────────────────────────

print("confidence")
g = X01Game(["A"], start_score=501)
g.record_score(20, "SINGLE", 20, 1, "20", confidence="confirmed")
g.record_score(20, "SINGLE", 20, 1, "20", confidence="provisional")
d = g.to_dict()
check("confidence carried into to_dict", d["turn"][0]["confidence"] == "confirmed")
check("provisional confidence carried", d["turn"][1]["confidence"] == "provisional")
check("undo preserves confidence", (g.undo(), g.to_dict()["turn"][0]["confidence"])[1] == "confirmed")

print("visit review (missing dart)")
g = X01Game(["A", "B"], start_score=501)
g.record_score(20, "SINGLE", 20, 1, "20")
g.record_score(5, "SINGLE", 5, 1, "5")           # only 2 darts detected, then collected
rv = g.enter_review()
check("enter_review pauses on a short visit", g.in_review() and rv["missing"] == 1)
check("review does NOT advance the player", g.current == 0 and len(g.turn) == 2)
check("review surfaced in to_dict", g.to_dict()["review"]["thrown"] == 2)
# user adds the missing dart manually -> completes the visit and advances
ev = g.add_review_dart(dartboard.score_detail(0, 130))   # a 20
check("add_review_dart completes visit", ev["turn_over"] and not g.in_review())
check("player advanced after completing visit", g.current == 1)
check("missing dart scored (501-45)", g.players[0].score == 456)

# confirm path: short visit confirmed as-thrown advances with the darts thrown
g = X01Game(["A", "B"], start_score=501)
g.record_score(20, "SINGLE", 20, 1, "20")
g.enter_review()
check("enter_review on 1 dart", g.review["missing"] == 2)
g.confirm_review()
check("confirm_review advances", g.current == 1 and not g.in_review())
check("confirmed visit kept its 20 (501-20)", g.players[0].score == 481)
gg = X01Game(["A"])
gg.record_score(1, "SINGLE", 1, 1, "1")
gg.record_score(1, "SINGLE", 1, 1, "1")
gg.record_score(1, "SINGLE", 1, 1, "1")
check("enter_review no-op on a full 3-dart turn", gg.enter_review() is None)


# ── serialisation ───────────────────────────────────────────────────────────

print("serialisation")
g = X01Game(["A", "B"], start_score=170)
d = g.to_dict()
check("to_dict has checkout for 170", d["checkout"] == ["T20", "T20", "DBull"])
check("to_dict players list", len(d["players"]) == 2)


print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
