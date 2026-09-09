"""How long a match is, and who has won it.

A round used to be one question and a match was however many of them somebody
felt like running. That is fine for a club night with a person at the front
deciding when to stop, and it declares no winner - which is the one thing a
game is for.

So the shape is taken from the thing it is practice for. A Technician or
General element is 35 questions; five rounds of eight is 40, which is near
enough to feel like the real length and divides into rounds that each mean
something. Extra is 50, and five rounds of twelve is 60 - half again as long
as the others and only ten over its own element, which the larger pool has the
material for.

Five rounds rather than eight of five, though the question count is much the
same either way. Eight rounds of five is a series of skirmishes; five rounds of
eight is long enough that a round can be lost early and won back, and short
enough that losing one matters. It also has an odd number of rounds, so it
ends.

**Winning.** Most rounds. Three of five ends it the moment it happens, whether
or not the remaining rounds are played, because they cannot change the answer.

**A drawn round** does not exist. Whoever answered most correctly takes it; on
equal correct answers the faster total time takes it, which needs no rule
explained to anybody - the quicker player simply wins it. Only a round nobody
scored in at all goes to nobody.

**Overtime.** With three or more players a match can end five rounds with
nobody holding a majority - two, two and one. Then the rounds go on, and a
player has to be two rounds clear to take it, because being one ahead at an
arbitrary moment is not the same as having won. If five overtime rounds pass
without anybody getting two clear, the players are offered a draw. There is
nothing to forfeit by accepting one; the offer is theatre, and theatre is
worth something at the end of a long evening.
"""

ROUNDS = 5

# By the class being played, and therefore by the element it is practice for.
QUESTIONS = {"technician": 8, "general": 8, "extra": 12}
DEFAULT_QUESTIONS = 8

# Once regulation is over, how far clear a player has to be, and how long the
# deadlock is allowed to run before somebody suggests everyone goes home.
OVERTIME_LEAD = 2
OVERTIME_PATIENCE = 5


def questions_per_round(difficulty=None):
    """How many questions make one round, for the class being played."""
    return QUESTIONS.get(str(difficulty or "").lower(), DEFAULT_QUESTIONS)


def length(difficulty=None):
    """How many questions the whole of regulation is."""
    return ROUNDS * questions_per_round(difficulty)


def round_winner(tallies):
    """Who took one round, from {entrant: {"correct": n, "ms": total}}.

    Most correct answers. On a tie, the faster total time - not because speed
    is the point, but because two players who got the same number right did
    not do equally well and somebody has to take the round. A round in which
    nobody answered anything correctly goes to nobody.
    """
    scored = {who: t for who, t in (tallies or {}).items()
              if (t or {}).get("correct")}
    if not scored:
        return None
    best = max(t["correct"] for t in scored.values())
    tied = [who for who, t in scored.items() if t["correct"] == best]
    if len(tied) == 1:
        return tied[0]
    # Sorted by time and then by entrant, so two players who somehow tie on
    # both get a stable answer rather than whichever way the dict fell.
    return min(tied, key=lambda who: (scored[who].get("ms") or 0, str(who)))


def verdict(won, rounds_played):
    """Where the match stands, from {entrant: rounds won} and rounds played.

    Returns a dict: `state` is one of "playing", "won" or "deadlocked",
    `winner` is set when there is one, and `why` says it in words.
    """
    won = dict(won or {})
    played = int(rounds_played or 0)
    if not won:
        return {"state": "playing", "winner": None, "overtime": False,
                "why": "nobody has taken a round yet"}

    ranked = sorted(won.items(), key=lambda kv: (-kv[1], str(kv[0])))
    leader, lead_wins = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    majority = ROUNDS // 2 + 1

    # Three of five ends it whenever it happens. The rounds still unplayed
    # cannot change it, and making people sit through them to be told what
    # they already know is not suspense.
    if lead_wins >= majority and lead_wins > runner_up and played <= ROUNDS:
        return {"state": "won", "winner": leader, "overtime": False,
                "why": f"{lead_wins} rounds of {ROUNDS}"}

    if played < ROUNDS:
        return {"state": "playing", "winner": None, "overtime": False,
                "why": f"round {played + 1} of {ROUNDS}"}

    # Regulation is over and nobody has a majority, which takes three players
    # or more. Two clear, or nothing.
    extra = played - ROUNDS
    if lead_wins - runner_up >= OVERTIME_LEAD:
        return {"state": "won", "winner": leader, "overtime": True,
                "why": f"two rounds clear after {played}"}
    if extra >= OVERTIME_PATIENCE:
        return {"state": "deadlocked", "winner": None, "overtime": True,
                "why": (f"{extra} rounds past regulation and nobody two "
                        f"clear - a draw is on offer")}
    return {"state": "playing", "winner": None, "overtime": True,
            "why": f"overtime round {extra + 1}, and two clear takes it"}
