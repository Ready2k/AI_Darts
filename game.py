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
        self.turn_conf = []           # detection confidence per dart (confirmed/provisional/...)
        self.turn_start_score = start_score
        self.winner = None            # Player who won the match, or None
        self.message = ""             # last human-readable event

        # Monotonic counter incremented on every dart — lets the frontend
        # reliably detect the 3rd dart of a visit even though self.turn resets
        # to [] synchronously in _advance_player.
        self.dart_seq = 0
        self.last_dart_label = None
        self.last_dart_pos = None
        # Keeps the just-completed visit's darts until the next visit starts
        # so display_turn in to_dict() can show all 3 darts.
        self._last_visit_turn = []
        self._last_visit_pos = []
        self._last_visit_conf = []

        # Set when a visit ends short (missing dart) — the engine pauses for the
        # user to add the dart or confirm. See enter_review().
        self.review = None

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

    def record_score(self, points, ring="SINGLE", segment=0, multiplier=1, label=None,
                     position=None, confidence=None):
        """Convenience entry point (mainly for tests) — builds a Hit and records it."""
        hit = Hit(points, label or str(points), ring, segment, multiplier)
        return self.record_hit(hit, position, confidence=confidence)

    def record_hit(self, hit, position=None, confidence=None):
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
                                         message=f"{hit.label} (needs double to start)",
                                         confidence=confidence)

        new_remaining = p.score - hit.points
        bust = self._is_bust(new_remaining, hit)

        if bust:
            return self._finish_dart(hit, position, bust=True, scored=False,
                                     message=f"{hit.label} — BUST", confidence=confidence)

        p.score = new_remaining
        if new_remaining == 0:
            return self._win_leg(hit, position, confidence=confidence)

        return self._finish_dart(hit, position, bust=False, scored=True,
                                 message=f"{hit.label} ({hit.points})",
                                 confidence=confidence)

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
        # A user-corrected dart is ground truth — mark it confirmed.
        return self.record_hit(hit, position, confidence="confirmed")

    # ── visit review (missing-dart prompt) ─────────────────────────────────
    # When a visit ends with fewer than 3 darts — a dart was missed by the
    # cameras, then the board was collected — the engine does NOT silently
    # advance (which would also misattribute the next visit's darts to this
    # player). Instead it PAUSES in a review state so the user can add the
    # missing dart (manual entry) or confirm the visit as thrown.

    def enter_review(self, reason="incomplete"):
        """Pause for the user after a short visit (1-2 darts). Does NOT advance.
        No-op (returns None) for a full/empty visit, when over, or already in
        review. Returns the review dict."""
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
        """Add a manually-entered missing dart during review. If it completes the
        visit (3 darts / bust / win) the review ends and the player advances;
        otherwise the review counts update and the pause continues."""
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
        """User confirms the short visit as thrown (the missing dart(s) left the
        board). Finalize the visit and advance. Returns a turn-over event."""
        if self.review is None:
            return None
        self.review = None
        if self.turn:
            self._push_undo()
            self._end_turn(bust=False)
        self.message = "Visit confirmed"
        return self._event(self.last_hit_placeholder(), bust=False, turn_over=True,
                           message=self.message)

    def last_hit_placeholder(self):
        """A minimal Hit for confirm_review's event (no new dart was thrown)."""
        return Hit(0, self.last_dart_label or "-", "MISS", 0, 1)

    def _is_bust(self, new_remaining, hit):
        if self.double_out:
            if new_remaining < 0 or new_remaining == 1:
                return True
            if new_remaining == 0 and not is_double(hit):
                return True
            return False
        return new_remaining < 0

    # ── turn / leg bookkeeping ─────────────────────────────────────────────

    def _finish_dart(self, hit, position, bust, scored, message, confidence=None):
        self.dart_seq += 1
        self.last_dart_label = hit.label
        self.last_dart_pos = list(position) if position else None
        self.turn.append(hit)
        self.turn_pos.append(position)
        self.turn_conf.append(confidence)
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
        self._last_visit_turn = list(self.turn)
        self._last_visit_pos = list(self.turn_pos)
        self._last_visit_conf = list(self.turn_conf)
        self.current = (self.current + 1) % len(self.players)
        self.turn = []
        self.turn_pos = []
        self.turn_conf = []
        self.turn_start_score = self.player.score

    def _win_leg(self, hit, position, confidence=None):
        p = self.player
        p.total_points += self.turn_start_score      # whole leg's worth scored
        p.total_darts  += len(self.turn) + 1
        self.dart_seq += 1
        self.last_dart_label = hit.label
        self.last_dart_pos = list(position) if position else None
        self.turn.append(hit)
        self.turn_pos.append(position)
        self.turn_conf.append(confidence)
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
        self._last_visit_turn = list(self.turn)
        self._last_visit_pos = list(self.turn_pos)
        self._last_visit_conf = list(self.turn_conf)
        for q in self.players:
            q.score = self.start_score
            q.opened = False
        self.leg_starter = (self.leg_starter + 1) % len(self.players)
        self.current = self.leg_starter
        self.turn = []
        self.turn_pos = []
        self.turn_conf = []
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
            "turn_conf": list(self.turn_conf),
            "turn_start_score": self.turn_start_score,
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
        self.turn_conf = list(snap.get("turn_conf", [None] * len(snap["turn"])))
        self.turn_start_score = snap["turn_start_score"]
        self.winner = next((p for p in self.players if p.name == snap["winner"]), None)
        self.message = snap["message"]
        self.dart_seq = snap.get("dart_seq", self.dart_seq)
        self.last_dart_label = snap.get("last_dart_label")
        self.last_dart_pos = snap.get("last_dart_pos")
        self._last_visit_turn = list(snap.get("_last_visit_turn", []))
        self._last_visit_pos = list(snap.get("_last_visit_pos", []))
        self._last_visit_conf = list(snap.get("_last_visit_conf", []))
        self.review = copy.deepcopy(snap.get("review"))
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
        # display_turn shows the current visit OR the just-completed visit when
        # self.turn has already been reset (3rd dart case). This lets the
        # frontend animate the 3rd dart even though self.turn is [].
        disp_turn = self.turn if self.turn else self._last_visit_turn
        disp_pos  = self.turn_pos if self.turn else self._last_visit_pos
        disp_conf = self.turn_conf if self.turn else self._last_visit_conf
        # pad confidence lists so a short/legacy list never truncates the zip
        t_conf = list(self.turn_conf) + [None] * (len(self.turn) - len(self.turn_conf))
        d_conf = list(disp_conf) + [None] * (len(disp_turn) - len(disp_conf))
        return {
            "start_score": self.start_score,
            "double_in": self.double_in,
            "double_out": self.double_out,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "current": self.current,
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
            "checkout": self.checkout_hint(),
            "message": self.message,
            "over": self.over,
            "winner": self.winner.name if self.winner else None,
            "players": [p.to_dict() for p in self.players],
            "review": self.review,
        }
