#!/usr/bin/env python3
"""Tests for the Autodarts adapter's CERTAIN integration layer — notation→Hit,
confidence mapping, message parsing, and applying events to the game (incl. the
takeout→review path). The only thing NOT covered here is the exact wire schema of
a specific board-manager version, which is finalised from `--capture`.

Run:  python3 test_autodarts_adapter.py
"""

import sys

import dartboard
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


# notation → Hit
def lab(h):
    return None if h is None else (h.label, h.points, h.ring, h.multiplier)

check("T20", lab(ad.notation_to_hit("T20")), ("Triple 20", 60, "TRIPLE", 3))
check("D12", lab(ad.notation_to_hit("d12")), ("Double 12", 24, "DOUBLE", 2))
check("S5", lab(ad.notation_to_hit("S5")), ("5", 5, "SINGLE", 1))
check("bare 18", lab(ad.notation_to_hit("18")), ("18", 18, "SINGLE", 1))
check("BULL", lab(ad.notation_to_hit("BULL")), ("Bullseye", 50, "INNER_BULL", 1))
check("OUTER", lab(ad.notation_to_hit("OUTER")), ("Bull", 25, "OUTER_BULL", 1))
check("MISS", lab(ad.notation_to_hit("MISS")), ("Miss", 0, "MISS", 1))
check("garbage -> None", ad.notation_to_hit("ZZ"), None)
check("bed_to_notation triple", ad.bed_to_notation("Triple", 20), "T20")
check("bed_to_notation double bull", ad.bed_to_notation("InnerBull", 50), "BULL")

# confidence float → level
check("0.95 confirmed", ad.confidence_level(0.95), "confirmed")
check("0.75 provisional", ad.confidence_level(0.75), "provisional")
check("0.40 low", ad.confidence_level(0.40), "low")
check("None confirmed (definitive)", ad.confidence_level(None), "confirmed")

# parse a (plausible) throw message → DartEvent
ev = ad._parse_message({"event": "throw",
                        "throw": {"segment": {"name": "T20", "bed": "Triple", "number": 20},
                                  "confidence": 0.94}})
check("parse throw kind", ev.kind, "throw")
check("parse throw hit", lab(ev.hit), ("Triple 20", 60, "TRIPLE", 3))
check("parse throw confidence", ev.confidence, 0.94)
check("parse flat score", ad._parse_message({"score": "D16", "confidence": 0.8}).hit.label,
      "Double 16")
check("parse takeout", ad._parse_message({"event": "takeout"}).kind, "takeout")

# record_into a real game (the consumer side)
g = X01Game(["A"], start_score=501)
ad.record_into(g, ad._parse_message({"score": "T20", "confidence": 0.95}))
check("throw scores into game (501-60)", g.players[0].score, 441)
check("confidence stored on the dart", g.to_dict()["turn"][0]["confidence"], "confirmed")
ad.record_into(g, ad._parse_message({"score": "S1", "confidence": 0.5}))
check("low-confidence dart still scored but flagged",
      g.to_dict()["turn"][1]["confidence"], "low")

# takeout on a SHORT visit opens review (the missing-dart prompt, robustly)
check("not in review yet", g.in_review(), False)
ad.record_into(g, ad._parse_message({"event": "takeout"}))
check("takeout with 2 darts -> review", g.in_review(), True)
check("review reports 1 missing", g.review["missing"], 1)

# takeout on a full visit does nothing
g2 = X01Game(["A"])
for _ in range(3):
    ad.record_into(g2, ad._parse_message({"score": "S20", "confidence": 0.99}))
check("takeout after a full visit -> no review", (ad.record_into(g2, ad._parse_message({"event": "takeout"})), g2.in_review())[1], False)


if __name__ == "__main__":
    print(f"\n{_p} passed, {_f} failed")
    sys.exit(1 if _f else 0)
