"""What a tournament is: how long it runs, and where its questions come from.

A tournament is not a quiz that stops when somebody gets bored. It is modelled
on the examination for the licence class being played, which is the only shape
of the material anybody has agreed on: the question pool is divided into
sections, the exam takes one question from each, and the number of sections in
a subelement *is* its weight on the paper. Draw the same way and the
proportions come out right without a second table to maintain and disagree
with the first.

Length is in blocks of twelve, and a winner is declared at the end of every
block rather than once at the end. Twelve questions is about ten minutes,
which is roughly how long a room will hold still, and a hall that declares
somebody every ten minutes gives a table that started badly three more
chances to be the table that won something.

Technician and General run three blocks. Extra runs four, which is a perk for
sitting the harder ticket rather than an accident of pool size - Extra's pool
is half again as big, but nobody would keep playing for an hour because the
pool said so.

What is deliberately *not* here yet is ascending difficulty. Ordering the
draw from easiest to hardest needs a measure of which questions are hard, and
this program does not have one: nothing in it has ever recorded how a
question went for the population rather than for one person. Inventing one
from question length or formula content would be a guess wearing the clothes
of data. Until there is a real one - the unit's own answer log is the honest
source, normalised per person so a fast reader and a slow one can be compared
- the draw is in blueprint order and says so, rather than claiming a ramp it
does not have. See `ordered()`.
"""
import random

from .content import get_pool

BLOCK = 12                 # questions between one winner and the next

# Blocks per tournament, by the difficulty key the net and the table both use.
# The commercial elements get three blocks as well: they are examinations of
# the same shape and nobody has asked for a longer one.
BLOCKS = {
    "technician": 3, "general": 3, "extra": 4,
    "mrop": 3, "grol": 3, "radar": 3,
}
DEFAULT_BLOCKS = 3


def blocks_for(difficulty):
    return BLOCKS.get(str(difficulty or "").lower(), DEFAULT_BLOCKS)


def length_for(difficulty):
    """How many questions the whole tournament runs to."""
    return blocks_for(difficulty) * BLOCK


def block_of(number):
    """Which block a question number falls in, counting from one."""
    return max(1, (int(number) - 1) // BLOCK + 1)


def ends_a_block(number):
    """True when this question is the last of its block, so a winner is due."""
    return int(number) > 0 and int(number) % BLOCK == 0


def draw(pool_id, count, rng=None):
    """`count` questions in the proportions the examination uses.

    One question per section, in a shuffled pass over the sections, repeating
    the pass if more are wanted than there are sections. That is the exam's
    own rule applied for as long as it is needed: a tournament shorter than
    the section count covers that fraction of the sections, and a longer one
    covers them all before it repeats any. No question is asked twice.

    Order within a pass is shuffled rather than left in section order, because
    a tournament that walks T1A, T1B, T1C down the pool reads as a list rather
    than a game, and everybody at the table can see what is coming.
    """
    pool = get_pool(pool_id)
    rng = rng or random.Random()
    sections = list(pool.section_order)
    if not sections:
        return []
    picked, used = [], set()
    while len(picked) < count:
        before = len(picked)
        order = sections[:]
        rng.shuffle(order)
        for code in order:
            if len(picked) >= count:
                break
            bank = [q for q in pool.by_section.get(code, [])
                    if q["id"] not in used]
            if not bank:
                continue
            question = bank[rng.randrange(len(bank))]
            used.add(question["id"])
            picked.append(question)
        if len(picked) == before:
            break          # the pool is smaller than the tournament asked for
    return picked


def ordered(questions, difficulty_of=None):
    """The draw in the order it will be asked.

    `difficulty_of` is a callable taking a question and returning a number,
    higher being harder, or None for a question nothing is known about. When
    it is absent, or knows too little to rank most of the draw, the blueprint
    order stands and `ramped` is False - which is the honest answer for a unit
    that has not been used yet, and the one a screen should be able to say out
    loud rather than implying a warm-up that is not there.
    """
    if difficulty_of is None:
        return list(questions), False
    scored = [(difficulty_of(q), q) for q in questions]
    known = [s for s, _ in scored if s is not None]
    # A ramp built from a quarter of the questions is not a ramp; it is three
    # quarters of the tournament in an order chosen by where the gaps fell.
    if len(known) < max(4, len(scored) * 0.6):
        return list(questions), False
    floor = min(known)
    return [q for _, q in sorted(
        scored, key=lambda sq: (sq[0] if sq[0] is not None else floor))], True


def plan(pool_id, difficulty, rng=None, difficulty_of=None):
    """The whole tournament, ready to be asked one question at a time."""
    wanted = length_for(difficulty)
    questions, ramped = ordered(draw(pool_id, wanted, rng), difficulty_of)
    return {
        "pool_id": pool_id,
        "difficulty": difficulty,
        "length": len(questions),
        "wanted": wanted,
        "block": BLOCK,
        "blocks": blocks_for(difficulty),
        "ramped": ramped,
        "questions": questions,
    }
