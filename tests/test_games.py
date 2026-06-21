"""Tests for the alternative game modes (games.py) + X01 master-in."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from dartboard import Hit
import games
import game as x01


def H(label, points, ring, segment, mult):
    return Hit(points, label, ring, segment, mult)


def single(n):  return H(f"S{n}", n, "SINGLE", n, 1)
def double(n):  return H(f"D{n}", 2 * n, "DOUBLE", n, 2)
def treble(n):  return H(f"T{n}", 3 * n, "TRIPLE", n, 3)
INNER_BULL = H("DBull", 50, "INNER_BULL", 25, 1)
OUTER_BULL = H("Bull", 25, "OUTER_BULL", 25, 1)


def test_count_up():
    g = games.create_game("Count Up", ["A", "B"], rounds=2)
    assert g.mode == "Count Up"
    # Round 1
    for h in (treble(20), single(20), single(5)):  # A: 85
        g.record_hit(h)
    assert g.current == 1
    for h in (single(1), single(1), single(1)):    # B: 3
        g.record_hit(h)
    # Round 2 — A again
    for h in (single(10), single(10), single(10)):  # A: 115
        g.record_hit(h)
    assert not g.over
    for h in (single(1), single(1), single(1)):    # B: 6
        g.record_hit(h)
    assert g.over
    assert g.winner.name == "A"
    assert g.players[0].score == 115
    print("count_up OK")


def test_around_the_clock():
    g = games.create_game("Around the Clock", ["A"])
    assert g.players[0].state["target"] == "1"
    g.record_hit(single(1))
    assert g.players[0].state["target"] == "2"
    g.record_hit(single(5))   # miss target 2
    assert g.players[0].state["target"] == "2"
    # blitz through to bull
    for n in range(2, 21):
        g.record_hit(single(n))
    assert g.players[0].state["target"] == "Bull"
    assert not g.over
    g.record_hit(OUTER_BULL)
    assert g.over and g.winner.name == "A"
    print("around_the_clock OK")


def test_shanghai_instant_win():
    g = games.create_game("Shanghai", ["A", "B"], rounds=7)
    assert g.target == 1
    # A throws S1, D1, T1 in one visit -> Shanghai
    g.record_hit(single(1))
    g.record_hit(double(1))
    g.record_hit(treble(1))
    assert g.over and g.winner.name == "A"
    print("shanghai_instant_win OK")


def test_shanghai_highest():
    g = games.create_game("Shanghai", ["A", "B"], rounds=1)
    # round 1 target=1
    g.record_hit(single(1)); g.record_hit(single(1)); g.record_hit(single(1))  # A=3
    assert g.current == 1
    g.record_hit(double(1)); g.record_hit(single(5)); g.record_hit(single(5))  # B=2
    assert g.over and g.winner.name == "A"
    print("shanghai_highest OK")


def test_cricket():
    g = games.create_game("Cricket", ["A", "B"])
    # A closes 20 with a treble, then scores 40 on it while B has it open
    g.record_hit(treble(20))   # 20 closed (3 marks), 0 pts
    assert g.players[0].state["marks"]["20"] == 3
    assert g.players[0].score == 0
    g.record_hit(treble(20))   # +60 (B still open)
    assert g.players[0].score == 60
    g.record_hit(single(1))    # no mark
    # B closes 20 -> now closed for both, A can't score on it
    g.record_hit(treble(20)); g.record_hit(single(1)); g.record_hit(single(1))
    g.record_hit(treble(20))   # A again: 20 closed for both -> no points
    assert g.players[0].score == 60
    print("cricket OK")


def test_cricket_win():
    g = games.create_game("Cricket", ["A", "B"])
    for t in [20, 19, 18, 17, 16, 15]:
        g.record_hit(treble(t)); g.record_hit(single(1)); g.record_hit(single(1))
        # B throws nothing useful
        g.record_hit(single(2)); g.record_hit(single(2)); g.record_hit(single(2))
    # bull: needs 3 marks -> DBull(2)+OuterBull(1)
    g.record_hit(INNER_BULL)   # 2 marks
    g.record_hit(OUTER_BULL)   # 3rd mark -> all closed, score 0 >= 0 -> win
    assert g.over and g.winner.name == "A"
    print("cricket_win OK")


def test_killer_hard():
    g = games.create_game("Killer", ["A", "B"], lives=3, killer_in="double")
    assert g.arm_mode == "double"
    assert g.players[0].state["number"] == 20
    # A not armed: hitting opponent does nothing
    g.record_hit(single(19)); g.record_hit(single(19)); g.record_hit(single(19))
    assert g.players[1].state["lives"] == 3
    # single 20 does NOT arm in hard mode
    g.record_hit(single(20)); g.record_hit(single(20)); g.record_hit(single(20))
    assert g.players[0].state["killer"] is False
    g.record_hit(double(20))            # arms on double
    assert g.players[0].state["killer"] is True
    g.record_hit(treble(19)); g.record_hit(single(1))  # B -3 -> out -> A wins
    assert g.over and g.winner.name == "A"
    print("killer_hard OK")


def test_killer_standard():
    g = games.create_game("Killer", ["A", "B"], lives=3)  # default = marks
    assert g.arm_mode == "marks"
    # A arms with 3 singles on own number (not consecutive needed, but here are)
    g.record_hit(single(20)); g.record_hit(single(20))
    assert g.players[0].state["killer"] is False and g.players[0].state["arm"] == 2
    g.record_hit(single(20))
    assert g.players[0].state["killer"] is True
    # B arms instantly with a treble of its number
    g.record_hit(treble(19)); g.record_hit(single(1)); g.record_hit(single(1))
    assert g.players[1].state["killer"] is True
    print("killer_standard OK")


def test_killer_self_harm():
    g = games.create_game("Killer", ["A", "B"], lives=3, killer_in="double")
    g.record_hit(double(20))            # A arms
    assert g.players[0].state["killer"]
    g.record_hit(double(20))            # A hits own 20 -> -2 lives
    assert g.players[0].state["lives"] == 1
    print("killer_self_harm OK")


def test_killer_ai():
    import ai
    # Hard: aims own double to arm
    g = games.create_game("Killer", [{"name": "A", "is_ai": True}, "B"], killer_in="double")
    assert ai.decide_target_label(g) == "D20"
    # Standard: aims own treble (3 marks at once)
    g2 = games.create_game("Killer", [{"name": "A", "is_ai": True}, "B"])
    assert ai.decide_target_label(g2) == "T20"
    g2.players[0].state["killer"] = True
    assert ai.decide_target_label(g2) == "T19"   # armed -> strongest foe
    print("killer_ai OK")


def test_master_in():
    g = x01.X01Game(["A"], start_score=101, check_in="master")
    assert g.double_in is True
    g.record_hit(single(20))   # doesn't open
    assert g.player.score == 101
    g.record_hit(treble(20))   # treble opens (master-in)
    assert g.player.score == 101 - 60
    print("master_in OK")


def test_undo_alt():
    g = games.create_game("Count Up", ["A", "B"])
    g.record_hit(single(20))
    assert g.players[0].score == 20
    g.undo()
    assert g.players[0].score == 0
    print("undo_alt OK")


def test_to_dict_shape():
    g = games.create_game("Cricket", ["A", "B"])
    d = g.to_dict()
    for k in ("mode", "mode_label", "current", "players", "turn",
              "display_turn", "over", "winner", "checkout", "review"):
        assert k in d, k
    assert d["players"][0]["name"] == "A"
    print("to_dict_shape OK")


if __name__ == "__main__":
    test_count_up()
    test_around_the_clock()
    test_shanghai_instant_win()
    test_shanghai_highest()
    test_cricket()
    test_cricket_win()
    test_killer_hard()
    test_killer_standard()
    test_killer_self_harm()
    test_killer_ai()
    test_master_in()
    test_undo_alt()
    test_to_dict_shape()
    print("\nAll games tests passed.")
