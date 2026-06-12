"""
X01 darts game engine (501 / 301 / 701 …).

Pure game logic — no cameras, no I/O. Feed it `dartboard.Hit` objects (or use
`record_score` with raw points for testing) and it tracks remaining scores,
busts, double-in / double-out, turns of three darts, multiple players, legs and
sets, per-player averages, and undo.

Designed to be driven by detect.py and serialised to JSON for the web UI.
"""

import copy

import checkout as checkout_mod
from dartboard import Hit, is_double


class Player:
    def __init__(self, name, start_score, is_ai=False, ai_level=None):
        self.name = name
        self.score = start_score          # remaining in the current leg
        self.legs = 0
        self.sets = 0
        self.opened = False               # has met double-in requirement this leg
        self.total_points = 0             # match totals, for averages
        self.total_darts = 0
        self.is_ai = is_ai
        self.ai_level = ai_level

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
            "opened": self.opened,
            "avg": round(self.three_dart_avg, 1),
            "darts": self.total_darts,
            "is_ai": self.is_ai,
            "ai_level": self.ai_level,
        }


class X01Game:
    def __init__(self, player_names, start_score=501,
                 double_in=False, double_out=True,
                 legs_to_win=1, sets_to_win=1):
        if not player_names:
            raise ValueError("need at least one player")
        self.start_score = start_score
        self.double_in   = double_in
        self.double_out  = double_out
        self.legs_to_win = legs_to_win
        self.sets_to_win = sets_to_win

        self.players = []
        for p in player_names:
            if isinstance(p, dict):
                self.players.append(Player(p["name"], start_score, is_ai=p.get("is_ai", False), ai_level=p.get("ai_level")))
            else:
                self.players.append(Player(p, start_score))
        self.current = 0
        self.leg_starter = 0          # who throws first this leg (rotates)
        self.turn = []                # Hits thrown in the current visit
        self.turn_pos = []            # board (x_mm, y_mm) per dart, or None
        self.turn_start_score = start_score
        self.winner = None            # Player who won the match, or None
        self.message = ""             # last human-readable event

        self._undo_stack = []

    # ── helpers ────────────────────────────────────────────────────────────

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
        """Suggested finish for the active player, or None."""
        if self.over:
            return None
        return checkout_mod.suggest(
            self.player.score, self.darts_left, self.double_out)

    # ── recording darts ────────────────────────────────────────────────────

    def record_score(self, points, ring="SINGLE", segment=0, multiplier=1, label=None, position=None):
        """Convenience entry point (mainly for tests) — builds a Hit and records it."""
        hit = Hit(points, label or str(points), ring, segment, multiplier)
        return self.record_hit(hit, position)

    def record_hit(self, hit, position=None):
        """
        Apply one dart. `position` is an optional (x_mm, y_mm) board coordinate
        kept for display / correction. Returns an event dict describing what
        happened:
            { dart, label, points, remaining, bust,
              leg_won, set_won, match_won, turn_over, message }
        """
        if self.over:
            return self._event(hit, bust=False, turn_over=False,
                               message="Game over")

        self._push_undo()
        p = self.player

        # Double-in: darts before the opening double score nothing.
        if self.double_in and not p.opened:
            if is_double(hit):
                p.opened = True
            else:
                return self._finish_dart(hit, position, bust=False, scored=False,
                                         message=f"{hit.label} (needs double to start)")

        new_remaining = p.score - hit.points
        bust = self._is_bust(new_remaining, hit)

        if bust:
            return self._finish_dart(hit, position, bust=True, scored=False,
                                     message=f"{hit.label} — BUST")

        p.score = new_remaining
        if new_remaining == 0:
            return self._win_leg(hit, position)

        return self._finish_dart(hit, position, bust=False, scored=True,
                                 message=f"{hit.label} ({hit.points})")

    def correct_last(self, hit, position=None):
        """
        Replace the most recently recorded dart with `hit` (a misread fix).
        Internally: undo the last dart, then apply the corrected one — so all
        score/bust/leg/turn consequences are recomputed. Returns the new event
        or None if there was no dart to correct.
        """
        if not self._undo_stack:
            return None
        self.undo()
        return self.record_hit(hit, position)

    def _is_bust(self, new_remaining, hit):
        if self.double_out:
            if new_remaining < 0 or new_remaining == 1:
                return True
            if new_remaining == 0 and not is_double(hit):
                return True
            return False
        return new_remaining < 0

    # ── turn / leg bookkeeping ─────────────────────────────────────────────

    def _finish_dart(self, hit, position, bust, scored, message):
        self.turn.append(hit)
        self.turn_pos.append(position)
        self.message = message
        turn_over = bust or len(self.turn) >= 3
        if turn_over:
            self._end_turn(bust)
        return self._event(hit, bust=bust, turn_over=turn_over, message=message)

    def _end_turn(self, bust):
        p = self.player
        if bust:
            p.score = self.turn_start_score      # revert this visit
        scored = self.turn_start_score - p.score
        p.total_points += scored
        p.total_darts  += len(self.turn)
        self._advance_player()

    def _advance_player(self):
        self.current = (self.current + 1) % len(self.players)
        self.turn = []
        self.turn_pos = []
        self.turn_start_score = self.player.score

    def _win_leg(self, hit, position):
        p = self.player
        p.total_points += self.turn_start_score      # whole leg's worth scored
        p.total_darts  += len(self.turn) + 1
        self.turn.append(hit)
        self.turn_pos.append(position)
        p.legs += 1

        set_won = match_won = False
        if p.legs >= self.legs_to_win:
            p.sets += 1
            set_won = True
            for q in self.players:
                q.legs = 0
            if p.sets >= self.sets_to_win:
                self.winner = p
                match_won = True
                self.message = f"{p.name} wins the match!"
                return self._event(hit, bust=False, turn_over=True,
                                   leg_won=True, set_won=True, match_won=True,
                                   message=self.message)
            self.message = f"{p.name} wins the set"
        else:
            self.message = f"{p.name} wins the leg"

        self._start_new_leg()
        return self._event(hit, bust=False, turn_over=True,
                           leg_won=True, set_won=set_won, match_won=match_won,
                           message=self.message)

    def _start_new_leg(self):
        for q in self.players:
            q.score = self.start_score
            q.opened = False
        self.leg_starter = (self.leg_starter + 1) % len(self.players)
        self.current = self.leg_starter
        self.turn = []
        self.turn_pos = []
        self.turn_start_score = self.start_score

    # ── undo ───────────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append(copy.deepcopy(self._snapshot()))
        if len(self._undo_stack) > 200:
            self._undo_stack.pop(0)

    def _snapshot(self):
        return {
            "players": [p.__dict__.copy() for p in self.players],
            "current": self.current,
            "leg_starter": self.leg_starter,
            "turn": list(self.turn),
            "turn_pos": list(self.turn_pos),
            "turn_start_score": self.turn_start_score,
            "winner": self.winner.name if self.winner else None,
            "message": self.message,
        }

    def undo(self):
        """Revert the last recorded dart. Returns True if something was undone."""
        if not self._undo_stack:
            return False
        snap = self._undo_stack.pop()
        for player, data in zip(self.players, snap["players"]):
            player.__dict__.update(data)
        self.current = snap["current"]
        self.leg_starter = snap["leg_starter"]
        self.turn = list(snap["turn"])
        self.turn_pos = list(snap["turn_pos"])
        self.turn_start_score = snap["turn_start_score"]
        self.winner = next((p for p in self.players if p.name == snap["winner"]), None)
        self.message = snap["message"]
        return True

    # ── serialisation ──────────────────────────────────────────────────────

    def _event(self, hit, bust, turn_over, message,
               leg_won=False, set_won=False, match_won=False):
        return {
            "dart": len(self.turn),
            "label": hit.label,
            "points": hit.points,
            "remaining": self.players[self.current].score if not turn_over else None,
            "bust": bust,
            "leg_won": leg_won,
            "set_won": set_won,
            "match_won": match_won,
            "turn_over": turn_over,
            "message": message,
        }

    def to_dict(self):
        return {
            "start_score": self.start_score,
            "double_in": self.double_in,
            "double_out": self.double_out,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "current": self.current,
            "darts_left": self.darts_left,
            "turn": [
                {"label": h.label, "points": h.points,
                 "pos": list(pos) if pos else None}
                for h, pos in zip(self.turn, self.turn_pos)
            ],
            "turn_points": sum(h.points for h in self.turn),
            "checkout": self.checkout_hint(),
            "message": self.message,
            "over": self.over,
            "winner": self.winner.name if self.winner else None,
            "players": [p.to_dict() for p in self.players],
        }
