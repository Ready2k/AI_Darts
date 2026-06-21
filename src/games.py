"""
Alternative darts game engines (Cricket, Around the Clock, Shanghai, Count Up).

These share the same external interface as `game.X01Game` so the detection loop,
web API, history writer and cinematic UI can drive any of them unchanged:

    record_hit(hit, position, confidence) -> event dict
    correct_last(hit, position)
    enter_review() / in_review() / add_review_dart() / confirm_review()
    undo()
    .over, .winner, .player, .darts_left, .checkout_hint(), .to_dict()

Scoring semantics live in each subclass's `_apply()` (and a couple of hooks);
all the turn / visit / undo / review / serialisation plumbing is shared in
`BaseGame`. Pure logic — no cameras, no I/O.
"""

import copy

from dartboard import Hit


class Player:
    def __init__(self, name, is_ai=False, ai_level=None):
        self.name = name
        self.is_ai = is_ai
        self.ai_level = ai_level
        self.score = 0            # headline number (points / progress, per mode)
        self.legs = 0
        self.sets = 0
        self.total_points = 0
        self.total_darts = 0
        self.state = {}           # mode-specific (cricket marks, ATC target, …)

    @property
    def three_dart_avg(self):
        if self.total_darts == 0:
            return 0.0
        return self.total_points / self.total_darts * 3

    def to_dict(self):
        return {
            "name": self.name,
            "score": self.score,
            "legs": self.legs,
            "sets": self.sets,
            "opened": True,
            "avg": round(self.three_dart_avg, 1),
            "darts": self.total_darts,
            "is_ai": self.is_ai,
            "ai_level": self.ai_level,
            "state": self.state,
        }


class BaseGame:
    """Shared turn/visit/undo/review machinery for the non-X01 modes."""

    mode = "base"

    def __init__(self, player_names, legs_to_win=1, sets_to_win=1):
        if not player_names:
            raise ValueError("need at least one player")
        self.legs_to_win = legs_to_win
        self.sets_to_win = sets_to_win
        # history.save_match compatibility
        self.start_score = 0
        self.double_in = False
        self.double_out = False

        self.players = []
        for p in player_names:
            if isinstance(p, dict):
                self.players.append(Player(p["name"], is_ai=p.get("is_ai", False),
                                           ai_level=p.get("ai_level")))
            else:
                self.players.append(Player(p))

        self.current = 0
        self.leg_starter = 0
        self.round_no = 1
        self.turn = []
        self.turn_pos = []
        self.turn_conf = []
        self.winner = None
        self.message = ""
        self.dart_seq = 0
        self.last_dart_label = None
        self.last_dart_pos = None
        self._last_visit_turn = []
        self._last_visit_pos = []
        self._last_visit_conf = []
        self.review = None
        self._undo_stack = []

        self._init_players()

    # ── subclass hooks ──────────────────────────────────────────────────────

    def _init_players(self):
        """Set up per-player mode state."""

    def _apply(self, player, hit):
        """Apply one dart to `player`. Return (points_scored, message).
        May set self.winner for an instant win."""
        raise NotImplementedError

    def _on_round_end(self):
        """Called after every player has thrown once (a full round)."""

    def mode_label(self):
        return self.mode

    def _player_summary(self):
        """Short status line for the active player (shown after a visit)."""
        return ""

    # ── helpers ─────────────────────────────────────────────────────────────

    @property
    def player(self):
        return self.players[self.current]

    @property
    def over(self):
        return self.winner is not None

    @property
    def darts_left(self):
        return 3 - len(self.turn)

    def checkout_hint(self):
        return None

    # ── recording darts ─────────────────────────────────────────────────────

    def record_score(self, points, ring="SINGLE", segment=0, multiplier=1,
                     label=None, position=None, confidence=None):
        hit = Hit(points, label or str(points), ring, segment, multiplier)
        return self.record_hit(hit, position, confidence=confidence)

    def record_hit(self, hit, position=None, confidence=None):
        if self.over:
            return self._event(hit, turn_over=False, message="Game over")

        self._push_undo()
        p = self.player
        points, msg = self._apply(p, hit)
        p.total_points += points

        self.dart_seq += 1
        self.last_dart_label = hit.label
        self.last_dart_pos = list(position) if position else None
        self.turn.append(hit)
        self.turn_pos.append(position)
        self.turn_conf.append(confidence)
        self.message = msg

        match_won = self.over
        turn_over = match_won or len(self.turn) >= 3 or self._visit_should_end(p)
        if turn_over and not match_won:
            self._end_turn()
        elif match_won:
            p.total_darts += len(self.turn)

        return self._event(hit, turn_over=turn_over, match_won=match_won,
                           message=msg)

    def correct_last(self, hit, position=None):
        if not self._undo_stack:
            return None
        self.undo()
        return self.record_hit(hit, position, confidence="confirmed")

    def _end_turn(self):
        p = self.player
        p.total_darts += len(self.turn)
        self._advance_player()

    def _advance_player(self):
        self._last_visit_turn = list(self.turn)
        self._last_visit_pos = list(self.turn_pos)
        self._last_visit_conf = list(self.turn_conf)
        self.current = (self.current + 1) % len(self.players)
        self.turn = []
        self.turn_pos = []
        self.turn_conf = []
        self._begin_visit()
        if self.current == self.leg_starter:
            self.round_no += 1
            self._on_round_end()

    def _begin_visit(self):
        """Per-visit reset hook (e.g. Shanghai's instant-win multiplier set)."""

    def _visit_should_end(self, player):
        """Subclass hook: end the visit early (before 3 darts), e.g. Killer when
        the thrower has just eliminated themselves."""
        return False

    # ── visit review (missing-dart prompt) ──────────────────────────────────

    def enter_review(self, reason="incomplete"):
        if self.over or self.review is not None:
            return self.review
        n = len(self.turn)
        if n <= 0 or n >= 3:
            return None
        self.review = {
            "reason": reason,
            "player": self.player.name,
            "thrown": n,
            "missing": 3 - n,
            "darts": [h.label for h in self.turn],
            "remaining": self.player.score,
        }
        self.message = (f"{self.player.name}: only {n} dart"
                        f"{'s' if n != 1 else ''} detected — add the missing "
                        f"dart or confirm")
        return self.review

    def in_review(self):
        return self.review is not None

    def add_review_dart(self, hit, position=None, confidence="confirmed"):
        if self.review is None:
            return None
        ev = self.record_hit(hit, position, confidence=confidence)
        if ev["turn_over"] or len(self.turn) >= 3:
            self.review = None
        else:
            self.review.update(
                thrown=len(self.turn), missing=3 - len(self.turn),
                darts=[h.label for h in self.turn], remaining=self.player.score)
        return ev

    def confirm_review(self):
        if self.review is None:
            return None
        self.review = None
        if self.turn:
            self._push_undo()
            self._end_turn()
        self.message = "Visit confirmed"
        return self._event(Hit(0, self.last_dart_label or "-", "MISS", 0, 1),
                           turn_over=True, message=self.message)

    # ── undo ─────────────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append(copy.deepcopy(self._snapshot()))
        if len(self._undo_stack) > 200:
            self._undo_stack.pop(0)

    def _snapshot(self):
        return {
            "players": [{**p.__dict__} for p in self.players],
            "current": self.current,
            "leg_starter": self.leg_starter,
            "round_no": self.round_no,
            "turn": list(self.turn),
            "turn_pos": list(self.turn_pos),
            "turn_conf": list(self.turn_conf),
            "winner": self.winner.name if self.winner else None,
            "message": self.message,
            "dart_seq": self.dart_seq,
            "last_dart_label": self.last_dart_label,
            "last_dart_pos": self.last_dart_pos,
            "_last_visit_turn": list(self._last_visit_turn),
            "_last_visit_pos": list(self._last_visit_pos),
            "_last_visit_conf": list(self._last_visit_conf),
            "review": copy.deepcopy(self.review),
        }

    def undo(self):
        if not self._undo_stack:
            return False
        snap = self._undo_stack.pop()
        for player, data in zip(self.players, snap["players"]):
            player.__dict__.update(copy.deepcopy(data))
        self.current = snap["current"]
        self.leg_starter = snap["leg_starter"]
        self.round_no = snap["round_no"]
        self.turn = list(snap["turn"])
        self.turn_pos = list(snap["turn_pos"])
        self.turn_conf = list(snap["turn_conf"])
        self.winner = next((p for p in self.players if p.name == snap["winner"]), None)
        self.message = snap["message"]
        self.dart_seq = snap["dart_seq"]
        self.last_dart_label = snap["last_dart_label"]
        self.last_dart_pos = snap["last_dart_pos"]
        self._last_visit_turn = list(snap["_last_visit_turn"])
        self._last_visit_pos = list(snap["_last_visit_pos"])
        self._last_visit_conf = list(snap["_last_visit_conf"])
        self.review = copy.deepcopy(snap["review"])
        return True

    # ── serialisation ────────────────────────────────────────────────────────

    def _event(self, hit, turn_over, message, match_won=False):
        return {
            "dart": len(self.turn),
            "label": hit.label,
            "points": hit.points,
            "remaining": self.player.score if not turn_over else None,
            "bust": False,
            "leg_won": match_won,
            "set_won": match_won,
            "match_won": match_won,
            "turn_over": turn_over,
            "message": message,
        }

    def to_dict(self):
        disp_turn = self.turn if self.turn else self._last_visit_turn
        disp_pos = self.turn_pos if self.turn else self._last_visit_pos
        disp_conf = self.turn_conf if self.turn else self._last_visit_conf
        t_conf = list(self.turn_conf) + [None] * (len(self.turn) - len(self.turn_conf))
        d_conf = list(disp_conf) + [None] * (len(disp_turn) - len(disp_conf))
        return {
            "mode": self.mode,
            "mode_label": self.mode_label(),
            "start_score": 0,
            "double_in": False,
            "double_out": False,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "current": self.current,
            "round": self.round_no,
            "darts_left": self.darts_left,
            "dart_seq": self.dart_seq,
            "turn": [
                {"label": h.label, "points": h.points,
                 "pos": list(pos) if pos else None, "confidence": conf}
                for h, pos, conf in zip(self.turn, self.turn_pos, t_conf)
            ],
            "display_turn": [
                {"label": h.label, "points": h.points,
                 "pos": list(pos) if pos else None, "confidence": conf}
                for h, pos, conf in zip(disp_turn, disp_pos, d_conf)
            ],
            "turn_points": sum(h.points for h in self.turn),
            "checkout": None,
            "message": self.message,
            "over": self.over,
            "winner": self.winner.name if self.winner else None,
            "players": [p.to_dict() for p in self.players],
            "review": self.review,
        }


# ── Around the Clock ─────────────────────────────────────────────────────────

class AroundTheClockGame(BaseGame):
    """Hit 1→20 then bull, in sequence. First to clear the bull wins.
    Any single/double/treble of the current target counts."""

    mode = "Around the Clock"
    SEQUENCE = list(range(1, 21)) + [25]

    def _init_players(self):
        for p in self.players:
            p.state = {"idx": 0, "target": self._label(0)}
            p.score = 0

    def _label(self, idx):
        if idx >= len(self.SEQUENCE):
            return "Done"
        n = self.SEQUENCE[idx]
        return "Bull" if n == 25 else str(n)

    def _hits_target(self, hit, target):
        if target == 25:
            return hit.ring in ("INNER_BULL", "OUTER_BULL")
        return hit.segment == target and hit.ring in ("SINGLE", "DOUBLE", "TRIPLE")

    def _apply(self, p, hit):
        idx = p.state["idx"]
        if idx >= len(self.SEQUENCE):
            return 0, "Already finished"
        target = self.SEQUENCE[idx]
        if self._hits_target(hit, target):
            idx += 1
            p.state["idx"] = idx
            p.state["target"] = self._label(idx)
            p.score = idx
            if idx >= len(self.SEQUENCE):
                self.winner = p
                return 0, f"{p.name} clears the board — game shot!"
            return 0, f"{p.name} hits {self._label(idx - 1)} → now on {self._label(idx)}"
        return 0, f"{hit.label} — still on {self._label(idx)}"

    def mode_label(self):
        return "Around the Clock · 1→20→Bull"


# ── Count Up (High Score) ────────────────────────────────────────────────────

class CountUpGame(BaseGame):
    """Most points over a fixed number of rounds. Every hit scores its value."""

    mode = "Count Up"

    def __init__(self, player_names, rounds=8, legs_to_win=1, sets_to_win=1):
        self.rounds = rounds
        super().__init__(player_names, legs_to_win, sets_to_win)

    def _init_players(self):
        for p in self.players:
            p.score = 0
            p.state = {}

    def _apply(self, p, hit):
        p.score += hit.points
        return hit.points, f"{hit.label} ({hit.points}) — total {p.score}"

    def _on_round_end(self):
        if self.round_no > self.rounds:
            self.winner = max(self.players, key=lambda q: q.score)
            self.message = f"{self.winner.name} wins with {self.winner.score}!"

    def mode_label(self):
        return f"Count Up · {self.rounds} rounds"

    def to_dict(self):
        d = super().to_dict()
        d["rounds"] = self.rounds
        return d


# ── Shanghai ─────────────────────────────────────────────────────────────────

class ShanghaiGame(BaseGame):
    """Round r → only number r counts (single=r, double=2r, treble=3r). Highest
    total after the final round wins. Hitting single+double+treble of the target
    in one visit is an instant 'Shanghai' win."""

    mode = "Shanghai"

    def __init__(self, player_names, rounds=7, legs_to_win=1, sets_to_win=1):
        self.rounds = max(1, min(20, rounds))
        super().__init__(player_names, legs_to_win, sets_to_win)

    def _init_players(self):
        for p in self.players:
            p.score = 0
            p.state = {"target": 1}
        self._turn_mults = set()

    @property
    def target(self):
        return min(self.round_no, self.rounds)

    def _begin_visit(self):
        self._turn_mults = set()
        for p in self.players:
            p.state["target"] = self.target

    def _apply(self, p, hit):
        target = self.target
        p.state["target"] = target
        if hit.segment == target and hit.ring in ("SINGLE", "DOUBLE", "TRIPLE"):
            mult = {"SINGLE": 1, "DOUBLE": 2, "TRIPLE": 3}[hit.ring]
            pts = target * mult
            p.score += pts
            self._turn_mults.add(mult)
            if {1, 2, 3} <= self._turn_mults:
                self.winner = p
                return pts, f"SHANGHAI! {p.name} wins outright on {target}"
            return pts, f"{hit.label} ({pts}) — total {p.score}"
        return 0, f"{hit.label} — needs {target}"

    def _on_round_end(self):
        if self.round_no > self.rounds:
            self.winner = max(self.players, key=lambda q: q.score)
            self.message = f"{self.winner.name} wins with {self.winner.score}!"

    def mode_label(self):
        return f"Shanghai · target {self.target}/{self.rounds}"

    def to_dict(self):
        d = super().to_dict()
        d["rounds"] = self.rounds
        d["target"] = self.target
        return d


# ── Cricket ──────────────────────────────────────────────────────────────────

class CricketGame(BaseGame):
    """Standard cricket. Close 20-15 + bull (3 marks each); marks beyond a close
    score points while at least one opponent has that number open. Win by closing
    everything with a points lead (or tie)."""

    mode = "Cricket"
    TARGETS = [20, 19, 18, 17, 16, 15, 25]

    def _init_players(self):
        for p in self.players:
            p.score = 0
            p.state = {"marks": {str(t): 0 for t in self.TARGETS}}

    def _target_of(self, hit):
        if hit.ring in ("INNER_BULL", "OUTER_BULL"):
            return 25
        if hit.segment in self.TARGETS and hit.ring in ("SINGLE", "DOUBLE", "TRIPLE"):
            return hit.segment
        return None

    def _marks_of(self, hit):
        if hit.ring == "INNER_BULL":
            return 2
        if hit.ring == "OUTER_BULL":
            return 1
        return {"SINGLE": 1, "DOUBLE": 2, "TRIPLE": 3}.get(hit.ring, 0)

    def _all_closed(self, p):
        return all(p.state["marks"][str(t)] >= 3 for t in self.TARGETS)

    def _check_win(self, p):
        if self._all_closed(p) and p.score >= max(q.score for q in self.players):
            self.winner = p
            self.message = f"{p.name} closes out and wins!"
            return True
        return False

    def _apply(self, p, hit):
        target = self._target_of(hit)
        if target is None:
            return 0, f"{hit.label} — no mark"
        key = str(target)
        marks = self._marks_of(hit)
        gained = 0
        label = "Bull" if target == 25 else str(target)
        was_closed = p.state["marks"][key] >= 3
        for _ in range(marks):
            if p.state["marks"][key] < 3:
                p.state["marks"][key] += 1
            else:
                # scoring: only if an opponent still has this number open
                if any(q.state["marks"][key] < 3 for q in self.players if q is not p):
                    p.score += target
                    gained += target
        if self._check_win(p):
            return gained, self.message
        now = p.state["marks"][key]
        to_close = 3 - now
        # Build a message that explains the closing model rather than a raw score.
        if gained:
            msg = f"{p.name} scores {gained} on {label}"
        elif now >= 3 and not was_closed:
            msg = f"{p.name} closes {label}!"
        elif to_close > 0:
            msg = f"{p.name} {label} — {to_close} more to close"
        else:
            # Already closed, no points (everyone has it closed → dead number)
            msg = f"{p.name} {label} closed (no points — all closed)"
        return gained, msg

    def mode_label(self):
        return "Cricket · 20-15 + Bull"


# ── Killer ───────────────────────────────────────────────────────────────────

class KillerGame(BaseGame):
    """Last player standing.

    • Each player is assigned a unique number and starts with `lives` lives.
    • Arm yourself to become a 'killer'. Two arming rules (`arm_mode`):
        - "double"  (Hard)     — hit the DOUBLE of your OWN number.
        - "marks"   (Standard) — land 3 marks on your number in total (single 1,
          double 2, treble 3; they don't need to be consecutive).
    • As a killer, hitting an opponent's number removes lives equal to the
      multiplier (single 1, double 2, treble 3).
    • Careful — once armed, hitting your OWN number costs YOU that many lives.
    • Drop to 0 lives and you're eliminated. Last player alive wins.
    """

    mode = "Killer"
    NUMBER_POOL = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

    def __init__(self, player_names, lives=3, arm_mode="marks",
                 legs_to_win=1, sets_to_win=1):
        self.lives0 = max(1, min(9, lives or 3))
        self.arm_mode = arm_mode if arm_mode in ("double", "marks") else "marks"
        super().__init__(player_names, legs_to_win, sets_to_win)

    def _init_players(self):
        for i, p in enumerate(self.players):
            num = self.NUMBER_POOL[i % len(self.NUMBER_POOL)]
            p.state = {"number": num, "lives": self.lives0, "killer": False,
                       "out": False, "arm": 0}
            p.score = self.lives0

    def _seg_mult(self, hit):
        """(segment, multiplier) for a numbered hit, or (None, 0). Bull is ignored
        in Killer (numbers are 1-20)."""
        if hit.ring in ("SINGLE", "DOUBLE", "TRIPLE"):
            return hit.segment, {"SINGLE": 1, "DOUBLE": 2, "TRIPLE": 3}[hit.ring]
        return None, 0

    def _owner_of(self, seg):
        for q in self.players:
            if q.state["number"] == seg and not q.state["out"]:
                return q
        return None

    def _alive(self):
        return [q for q in self.players if not q.state["out"]]

    def _check_win(self):
        alive = self._alive()
        if len(self.players) > 1 and len(alive) == 1:
            self.winner = alive[0]
            self.message = f"{self.winner.name} is the last one standing — winner!"
            return True
        return False

    def _eliminate(self, q):
        q.state["out"] = True
        q.state["lives"] = 0
        q.score = 0

    def _apply(self, p, hit):
        seg, mult = self._seg_mult(hit)
        own = p.state["number"]
        label = str(own)

        if seg is None:
            return 0, f"{hit.label} — off target"

        # Phase 1 — arm yourself.
        if not p.state["killer"]:
            if self.arm_mode == "double":
                if seg == own and hit.ring == "DOUBLE":
                    p.state["killer"] = True
                    return 0, f"{p.name} is ARMED on double {own} — killer!"
                if seg == own:
                    return 0, f"{p.name} {own} — need DOUBLE {own} to arm"
                return 0, f"{hit.label} — {p.name} must arm on double {own}"
            # marks: accumulate 3 marks on your own number to arm.
            if seg == own:
                p.state["arm"] = min(3, p.state["arm"] + mult)
                if p.state["arm"] >= 3:
                    p.state["killer"] = True
                    return 0, f"{p.name} is ARMED on {own} — killer!"
                need = 3 - p.state["arm"]
                return 0, f"{p.name} {own} — {need} more to arm"
            return 0, f"{hit.label} — {p.name} must arm on {own}"

        # Phase 2 — armed killer.
        if seg == own:
            # Self-harm: hitting your own number now costs you lives.
            p.state["lives"] = max(0, p.state["lives"] - mult)
            p.score = p.state["lives"]
            if p.state["lives"] == 0:
                self._eliminate(p)
                self._check_win()
                return 0, f"{p.name} hit their OWN {own} and is OUT!"
            return 0, f"{p.name} hit their own {own} — lost {mult} (now {p.state['lives']})"

        victim = self._owner_of(seg)
        if victim is None:
            return 0, f"{hit.label} — no one on {seg}"
        victim.state["lives"] = max(0, victim.state["lives"] - mult)
        victim.score = victim.state["lives"]
        if victim.state["lives"] == 0:
            self._eliminate(victim)
            if self._check_win():
                return 0, self.message
            return 0, f"{p.name} KNOCKS OUT {victim.name} ({victim.state['number']})!"
        return 0, f"{p.name} takes {mult} off {victim.name} (now {victim.state['lives']})"

    def assign_numbers(self, numbers):
        """Set players' numbers (from the spin-the-wheel pre-game). `numbers` is a
        list aligned to players, or a {name: number} dict. Only valid before play
        (resets arm/killer just in case). Returns True on success."""
        if isinstance(numbers, dict):
            pairs = [(p, numbers.get(p.name)) for p in self.players]
        else:
            pairs = list(zip(self.players, numbers or []))
        for p, n in pairs:
            if n is not None:
                p.state["number"] = int(n)
            p.state["arm"] = 0
            p.state["killer"] = False
        return True

    def _visit_should_end(self, p):
        # If the thrower eliminated themselves, end their visit immediately.
        return p.state["out"]

    def _advance_player(self):
        self._last_visit_turn = list(self.turn)
        self._last_visit_pos = list(self.turn_pos)
        self._last_visit_conf = list(self.turn_conf)
        n = len(self.players)
        nxt = self.current
        for _ in range(n):
            nxt = (nxt + 1) % n
            if not self.players[nxt].state["out"]:
                break
        self.current = nxt
        self.turn = []
        self.turn_pos = []
        self.turn_conf = []

    def mode_label(self):
        arm = "double to arm" if self.arm_mode == "double" else "3 marks to arm"
        return f"Killer · {self.lives0} lives · {arm}"

    def to_dict(self):
        d = super().to_dict()
        d["lives"] = self.lives0
        d["arm_mode"] = self.arm_mode
        return d


# ── factory ──────────────────────────────────────────────────────────────────

def create_game(mode, players, **opts):
    """Build a game by mode name. `opts` may include rounds, legs_to_win,
    sets_to_win. Returns a game instance or None if `mode` isn't a non-X01 mode
    handled here (the caller falls back to X01Game)."""
    legs = opts.get("legs_to_win", 1) or 1
    sets = opts.get("sets_to_win", 1) or 1
    m = (mode or "").strip().lower()
    if m in ("around the clock", "around-the-clock", "atc", "clock"):
        return AroundTheClockGame(players, legs_to_win=legs, sets_to_win=sets)
    if m in ("count up", "count-up", "countup", "high score", "highscore"):
        return CountUpGame(players, rounds=opts.get("rounds") or 8,
                           legs_to_win=legs, sets_to_win=sets)
    if m == "shanghai":
        return ShanghaiGame(players, rounds=opts.get("rounds") or 7,
                            legs_to_win=legs, sets_to_win=sets)
    if m == "cricket":
        return CricketGame(players, legs_to_win=legs, sets_to_win=sets)
    if m == "killer":
        return KillerGame(players, lives=opts.get("lives") or 3,
                          arm_mode=opts.get("killer_in") or "marks",
                          legs_to_win=legs, sets_to_win=sets)
    return None
