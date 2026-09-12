"""What every screen in the hall shows when it is not showing a question.

Net control drives a room. Between rounds the room's screens - the board at
the front, the table screens, the phones - used to show a result and then
nothing, and a dead screen at a hamfest is an invitation to find something
else to do. This is the host's hand on all of them at once:

* **Announcements**, addressed. To everyone, to one table, or to one seat;
  a *notice* that stands for a few seconds, or an *urgent* one that stays
  until the host clears it and comes back on a timer if asked. "Lost child
  at the ARRL booth" is urgent and for everyone; "You won the round" is a
  notice for one seat, and "Skippy won the round" the same notice for
  everybody else.
* **Attention**: one press blanks every table to a message while the host
  talks. Cleared by the host, not by a clock.
* **The deck**: what plays when no round is up - trivia from the decks in
  :mod:`elmer.trivia`, the standings, the sponsors' cards, the club's
  notices, the join code, what is next on the programme. Net control picks
  the card and every screen shows the same card at the same moment, which
  is what makes it a show rather than a screensaver.
* **Mode**: whether the hall is playing, studying or between things. In
  study mode the host names a focus - "everyone: T5 for ten minutes" - and
  the screens carry it.
* **The programme**: the evening as a list of steps the host walks with one
  button.

Nothing here decides a question or scores an answer; that stays in
:mod:`elmer.netcontrol`. This is carried to the units in the check-in reply
they already poll for once a second, so the whole of it costs the network
nothing it was not already paying.

Sponsors and notices are the event's own - files the host puts on this unit,
words the host typed. They persist under the state directory so an evening
set up on Tuesday is still set up on Saturday, and none of it ever leaves
the unit.
"""
import json
import logging
import random
import re
import threading
import time
from pathlib import Path

from . import trivia
from .paths import STATE

log = logging.getLogger("elmer")

NOTICE, URGENT = "notice", "urgent"
WEIGHTS = (NOTICE, URGENT)
NOTICE_SECONDS = 20.0            # how long a notice stands
URGENT_REPEAT = 60.0             # how often an urgent one comes back, if asked

PLAY, STUDY, INTERMISSION = "play", "study", "intermission"
MODES = (PLAY, STUDY, INTERMISSION)

DEFAULT_DWELL = 12.0             # seconds a card stands
MIN_DWELL, MAX_DWELL = 5.0, 60.0

# The kinds of card the deck can hold, and which are on by default. Trivia
# decks are the ones in trivia.DECKS; the rest are the hall's own.
TRIVIA_DECKS = list(trivia.DECKS)
CARD_KINDS = ["standings", "sponsor", "notice", "join", "programme"]
DEFAULT_DECK = {**{d: True for d in TRIVIA_DECKS},
                **{k: True for k in CARD_KINDS}}

MAX_TEXT = 400
MAX_TITLE = 80
HOME = STATE / "show"
ASSETS = HOME / "assets"
SETTINGS = HOME / "show.json"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_ASSET_MB = 8


def _now():
    return time.time()


def _clean(text, limit=MAX_TEXT):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


class Show:
    """The host's hand on every screen in the hall."""

    def __init__(self, rng=None):
        self.lock = threading.RLock()
        self.rng = rng or random.Random()
        # -- announcements
        self.announcements = []
        self._next_id = 1
        self.attention = None            # {"text", "at"} or None
        # -- the deck
        self.deck = dict(DEFAULT_DECK)
        self.dwell = DEFAULT_DWELL
        self._card = None
        self._cycle_at = 0               # position in the card cycle
        self._trivia_at = 0              # which trivia deck is next
        self._last_trivia = {}           # deck -> last text shown
        self._sponsor_at = 0
        self._notice_at = 0
        # -- the event's own content
        self.sponsors = []               # {"id","name","blurb","url","file","weight"}
        self.notices = []                # {"id","title","text","url"}
        # -- mode and focus
        self.mode = PLAY
        self.focus = None                # {"section","title","text","until"}
        # -- the programme
        self.programme = []
        self.step = -1
        self._step_at = 0.0

    # ------------------------------------------------------- announcements

    def announce(self, text, weight=NOTICE, unit=None, seat=None,
                 seconds=None, repeat=None, now=None):
        """Say something to everyone, to one table, or to one seat.

        A notice stands for `seconds` (default NOTICE_SECONDS). An urgent one
        stands until cleared; with `repeat` it stands for `seconds` every
        `repeat` seconds instead, so a lost child comes back on the screens
        every minute without the host pressing anything.
        """
        text = _clean(text)
        if not text:
            raise ValueError("nothing to say")
        weight = weight if weight in WEIGHTS else NOTICE
        now = _now() if now is None else now
        with self.lock:
            item = {
                "id": self._next_id, "text": text, "weight": weight,
                "unit": (str(unit)[:40] if unit else None),
                "seat": (_clean(seat, 60) if seat else None),
                "at": now,
                "seconds": (float(seconds) if seconds else
                            (None if weight == URGENT and not repeat
                             else NOTICE_SECONDS)),
                "repeat": (max(15.0, float(repeat)) if repeat else None),
            }
            self._next_id += 1
            self.announcements.append(item)
            # Nothing older than an hour is still an announcement. Urgent
            # ones without a clock are kept until cleared.
            self.announcements = [
                a for a in self.announcements
                if a["seconds"] is None or a["repeat"] or now - a["at"] < 3600]
            log.info("show: %s announcement %d to %s: %s", weight, item["id"],
                     seat or unit or "everyone", text[:80])
            return dict(item)

    def clear(self, ann_id):
        with self.lock:
            before = len(self.announcements)
            self.announcements = [a for a in self.announcements
                                  if a["id"] != int(ann_id)]
            return len(self.announcements) < before

    def clear_all(self):
        with self.lock:
            self.announcements = []
            self.attention = None

    def hold_attention(self, text, now=None):
        """Blank every table to this, until released. None releases."""
        with self.lock:
            text = _clean(text)
            self.attention = ({"text": text, "at": _now() if now is None else now}
                              if text else None)
            log.info("show: attention %s", "held: " + text[:60] if text else "released")
            return self.attention

    def _showing(self, item, now):
        age = now - item["at"]
        if age < 0:
            return False
        if item["repeat"]:
            return (age % item["repeat"]) < (item["seconds"] or NOTICE_SECONDS)
        if item["seconds"] is None:
            return True
        return age < item["seconds"]

    def announcements_for(self, unit=None, seat=None, now=None):
        """What this screen should be showing right now, most urgent first.

        A table screen (no seat) gets what is for everyone and for its table;
        a phone gets those plus what is for its seat. Nothing meant for one
        seat ever reaches another - the winner's line is the winner's.
        """
        now = _now() if now is None else now
        with self.lock:
            out = []
            for a in self.announcements:
                if not self._showing(a, now):
                    continue
                if a["unit"] and a["unit"] != unit:
                    continue
                # seat "*" is the unit itself asking: it takes every seat's
                # line for its table and hands each to the right phone.
                if a["seat"] and seat != "*" and (
                        seat is None or a["seat"].lower() != seat.lower()):
                    continue
                out.append({k: v for k, v in a.items() if k != "unit"}
                           | {"mine": bool(a["seat"])})
            out.sort(key=lambda a: (a["weight"] != URGENT, -a["at"]))
            return out

    def pending(self, now=None):
        """Everything still live, for the host's list."""
        now = _now() if now is None else now
        with self.lock:
            return [dict(a, showing=self._showing(a, now))
                    for a in self.announcements
                    if a["seconds"] is None or a["repeat"]
                    or now - a["at"] < a["seconds"]]

    # ---------------------------------------------------------------- deck

    def set_deck(self, flags=None, dwell=None):
        with self.lock:
            for key, on in (flags or {}).items():
                if key in self.deck:
                    self.deck[key] = bool(on)
            if dwell is not None:
                self.dwell = min(MAX_DWELL, max(MIN_DWELL, float(dwell)))
            self._card = None            # start the cycle over with the new deck
            return {"deck": dict(self.deck), "dwell": self.dwell}

    def _cycle(self, standings, join):
        """The order cards come in: a trivia card between every other kind,
        so a sponsor's card never follows a sponsor's card and the room is
        never three standings in a row."""
        trivia_on = [d for d in TRIVIA_DECKS if self.deck.get(d)]
        others = []
        if self.deck.get("sponsor") and self.sponsors:
            others.append("sponsor")
        if self.deck.get("standings") and standings:
            others.append("standings")
        if self.deck.get("notice") and self.notices:
            others.append("notice")
        if self.deck.get("join") and join:
            others.append("join")
        if self.deck.get("programme") and self.programme:
            others.append("programme")
        if self.mode == STUDY and self.focus:
            others.insert(0, "focus")
        cycle = []
        for kind in others:
            if trivia_on:
                cycle.append("trivia")
            cycle.append(kind)
        if not cycle:
            cycle = ["trivia"] if trivia_on else []
        # Sponsors twice as often as the rest of the hall's own cards: they
        # paid for the room, and a card every few minutes is what they were
        # promised.
        if "sponsor" in cycle and len(self.sponsors) > 1 and len(cycle) > 4:
            cycle.insert(len(cycle) // 2, "sponsor")
        # In study the focus leads and comes back mid-pass: it is what the
        # room is meant to be doing, and a card that says so every minute
        # or two is the instructor's voice while they are at a table.
        if "focus" in cycle:
            cycle.remove("focus")
            cycle.insert(0, "focus")
            if len(cycle) > 4:
                cycle.insert(len(cycle) // 2 + 1, "focus")
        return cycle

    def _make(self, kind, standings, join, now):
        card = {"kind": kind, "since": now, "dwell": self.dwell}
        if kind == "trivia":
            decks = [d for d in TRIVIA_DECKS if self.deck.get(d)]
            deck = decks[self._trivia_at % len(decks)]
            self._trivia_at += 1
            drawn = trivia.draw(self.rng, self._last_trivia.get(deck), deck)
            self._last_trivia[deck] = drawn["text"]
            card.update({"deck": deck, "text": drawn["text"],
                         "about": drawn["about"]})
        elif kind == "sponsor":
            # Weight is repetition: a weight-2 sponsor appears twice per pass.
            order = [s for s in self.sponsors for _ in range(max(1, int(s.get("weight") or 1)))]
            s = order[self._sponsor_at % len(order)]
            self._sponsor_at += 1
            card.update({"name": s["name"], "blurb": s.get("blurb", ""),
                         "url": s.get("url", ""), "file": s.get("file")})
        elif kind == "notice":
            n = self.notices[self._notice_at % len(self.notices)]
            self._notice_at += 1
            card.update({"title": n["title"], "text": n["text"],
                         "url": n.get("url", "")})
        elif kind == "standings":
            card.update({"rows": standings[:6]})
        elif kind == "join":
            card.update({"join": join})
        elif kind == "programme":
            card.update(self.programme_view())
        elif kind == "focus":
            card.update({"focus": dict(self.focus)})
        return card

    def card(self, now=None, standings=None, join=None):
        """The card every screen shows right now; a new one when the dwell is up."""
        now = _now() if now is None else now
        with self.lock:
            live = self._card
            if live and now - live["since"] < live["dwell"] and live.get("cycle_key") == self._cycle_key(standings, join):
                # The standings move between rounds; the card keeps up.
                if live["kind"] == "standings" and standings is not None:
                    live["rows"] = standings[:6]
                return live
            cycle = self._cycle(standings, join)
            if not cycle:
                self._card = None
                return None
            kind = cycle[self._cycle_at % len(cycle)]
            self._cycle_at += 1
            card = self._make(kind, standings or [], join, now)
            card["id"] = f"{int(now)}-{self._cycle_at}"
            card["cycle_key"] = self._cycle_key(standings, join)
            self._card = card
            return card

    def _cycle_key(self, standings, join):
        return (bool(standings), bool(join), self.mode, len(self.sponsors),
                len(self.notices), len(self.programme))

    # ---------------------------------------------- sponsors and notices

    def add_sponsor(self, name, blurb="", url="", file=None, weight=1):
        name = _clean(name, MAX_TITLE)
        if not name:
            raise ValueError("a sponsor needs a name")
        with self.lock:
            item = {"id": self._next_id, "name": name,
                    "blurb": _clean(blurb), "url": _clean(url, 200),
                    "file": file, "weight": max(1, min(3, int(weight or 1)))}
            self._next_id += 1
            self.sponsors.append(item)
            self._card = None
            self.save()
            return dict(item)

    def remove_sponsor(self, sponsor_id):
        with self.lock:
            gone = [s for s in self.sponsors if s["id"] == int(sponsor_id)]
            self.sponsors = [s for s in self.sponsors if s["id"] != int(sponsor_id)]
            for s in gone:
                if s.get("file"):
                    try:
                        (ASSETS / s["file"]).unlink()
                    except OSError:
                        pass
            self._card = None
            self.save()
            return bool(gone)

    def add_notice(self, title, text, url=""):
        title, text = _clean(title, MAX_TITLE), _clean(text)
        if not (title or text):
            raise ValueError("a notice needs words")
        with self.lock:
            item = {"id": self._next_id, "title": title or "Notice",
                    "text": text, "url": _clean(url, 200)}
            self._next_id += 1
            self.notices.append(item)
            self._card = None
            self.save()
            return dict(item)

    def remove_notice(self, notice_id):
        with self.lock:
            before = len(self.notices)
            self.notices = [n for n in self.notices if n["id"] != int(notice_id)]
            self._card = None
            self.save()
            return len(self.notices) < before

    # ------------------------------------------------------ mode and focus

    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        with self.lock:
            self.mode = mode
            if mode != STUDY:
                self.focus = None
            self._card = None
            log.info("show: hall mode %s", mode)
            return mode

    def set_focus(self, section=None, title=None, text=None, minutes=None,
                  now=None):
        """What the room is studying, said on every screen. None clears."""
        now = _now() if now is None else now
        with self.lock:
            if not (section or text):
                self.focus = None
            else:
                self.focus = {
                    "section": _clean(section, 12) or None,
                    "title": _clean(title, MAX_TITLE),
                    "text": _clean(text),
                    "until": (now + 60.0 * float(minutes)) if minutes else None,
                    "at": now,
                }
                self.mode = STUDY
            self._card = None
            return self.focus

    def focus_view(self, now=None):
        now = _now() if now is None else now
        with self.lock:
            if not self.focus:
                return None
            f = dict(self.focus)
            f["remaining"] = (max(0, int(f["until"] - now)) if f["until"] else None)
            return f

    # ----------------------------------------------------------- programme

    def set_programme(self, steps):
        """The evening as a list. Each step is {"kind", ...}; see STEP_KINDS."""
        clean = []
        for s in steps or []:
            kind = str((s or {}).get("kind") or "").lower()
            if kind not in STEP_KINDS:
                continue
            step = {"kind": kind, "label": _clean(s.get("label"), MAX_TITLE)
                    or STEP_KINDS[kind]}
            for key in ("minutes", "rounds", "seconds"):
                if s.get(key) not in (None, ""):
                    try:
                        step[key] = max(0, float(s[key]))
                    except (TypeError, ValueError):
                        pass
            for key in ("text", "difficulty", "section", "mode"):
                if s.get(key):
                    step[key] = _clean(s[key])
            clean.append(step)
        with self.lock:
            self.programme = clean
            self.step = -1
            self._card = None
            return list(clean)

    def advance(self, now=None):
        """Move to the next step and return it, or None past the end."""
        now = _now() if now is None else now
        with self.lock:
            if self.step + 1 >= len(self.programme):
                self.step = len(self.programme)
                return None
            self.step += 1
            self._step_at = now
            self._card = None
            step = dict(self.programme[self.step])
            log.info("show: programme step %d/%d - %s", self.step + 1,
                     len(self.programme), step["label"])
            return step

    def programme_view(self, now=None):
        now = _now() if now is None else now
        with self.lock:
            cur = (self.programme[self.step]
                   if 0 <= self.step < len(self.programme) else None)
            nxt = (self.programme[self.step + 1]
                   if self.step + 1 < len(self.programme) else None)
            return {"step": self.step + 1, "of": len(self.programme),
                    "now": cur and cur["label"], "next": nxt and nxt["label"],
                    "since": (now - self._step_at) if cur else None,
                    "steps": [s["label"] for s in self.programme]}

    # ------------------------------------------------------------ for units

    def for_unit(self, unit=None, standings=None, join=None, now=None):
        """Everything one unit's screens need, in one check-in reply."""
        now = _now() if now is None else now
        with self.lock:
            return {
                "mode": self.mode,
                "focus": self.focus_view(now),
                "attention": dict(self.attention) if self.attention else None,
                # A unit gets its seats' lines too and hands them out itself;
                # the board (no unit) gets none of them.
                "announcements": self.announcements_for(unit, "*" if unit else None, now),
                "card": self.card(now, standings, join),
                "programme": self.programme_view(now) if self.programme else None,
            }

    def host_view(self, now=None):
        now = _now() if now is None else now
        with self.lock:
            return {
                "mode": self.mode, "focus": self.focus_view(now),
                "attention": dict(self.attention) if self.attention else None,
                "announcements": self.pending(now),
                "deck": dict(self.deck), "dwell": self.dwell,
                "decks": TRIVIA_DECKS, "kinds": CARD_KINDS,
                "sponsors": [dict(s) for s in self.sponsors],
                "notices": [dict(n) for n in self.notices],
                "programme": self.programme_view(now),
                "steps": [dict(s) for s in self.programme],
                "step_kinds": dict(STEP_KINDS),
                "card": self._card,
            }

    # --------------------------------------------------------- persistence

    def save(self):
        """The event's own content, kept between nets and across restarts."""
        with self.lock:
            data = {"deck": self.deck, "dwell": self.dwell,
                    "sponsors": self.sponsors, "notices": self.notices,
                    "programme": self.programme, "next_id": self._next_id}
        try:
            HOME.mkdir(parents=True, exist_ok=True)
            SETTINGS.write_text(json.dumps(data, indent=1))
        except OSError as exc:
            log.warning("show: could not save %s: %s", SETTINGS, exc)

    @classmethod
    def load(cls, rng=None):
        show = cls(rng)
        try:
            data = json.loads(SETTINGS.read_text())
        except (OSError, ValueError):
            return show
        with show.lock:
            for key, on in (data.get("deck") or {}).items():
                if key in show.deck:
                    show.deck[key] = bool(on)
            try:
                show.dwell = min(MAX_DWELL, max(MIN_DWELL, float(data.get("dwell") or DEFAULT_DWELL)))
            except (TypeError, ValueError):
                pass
            show.sponsors = [s for s in data.get("sponsors") or []
                             if isinstance(s, dict) and s.get("name")]
            show.notices = [n for n in data.get("notices") or []
                            if isinstance(n, dict) and (n.get("title") or n.get("text"))]
            show.programme = [s for s in data.get("programme") or []
                              if isinstance(s, dict) and s.get("kind") in STEP_KINDS]
            show._next_id = max(int(data.get("next_id") or 1),
                                1 + max([0] + [int(x.get("id", 0)) for x in show.sponsors + show.notices]))
        return show


# The steps a programme is made of, with the word for each on a screen.
STEP_KINDS = {
    "intermission": "Intermission",
    "rounds": "Tournament rounds",
    "shootout": "Shootout",
    "study": "Study",
    "announce": "Announcement",
    "certificates": "Certificates",
    "thanks": "Thanks",
}


def asset_name(filename):
    """A safe file name for a sponsor's card on this unit, or None."""
    name = Path(str(filename or "")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem).strip("-.")[:60]
    ext = Path(name).suffix.lower()
    if not stem or ext not in IMAGE_TYPES:
        return None
    return f"{stem}{ext}"
