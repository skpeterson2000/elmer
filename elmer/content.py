"""Loads the built question pools and answers questions about their structure."""
import json
import random
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL_DIR = ROOT / "data" / "pools"

# Choices that only make sense in last position; real exams keep them there.
_STICKY_LAST = ("all these choices are correct", "all of these choices are correct",
                "none of these choices is correct", "none of these answers are correct",
                "all of the above", "none of the above", "both a and b")


class Pool:
    def __init__(self, data):
        self.__dict__.update(data)
        self.by_id = {q["id"]: q for q in self.questions}
        self.by_section = {}
        for q in self.questions:
            self.by_section.setdefault(q["section"], []).append(q)
        self.section_meta = {s["code"]: s for s in self.sections}
        self.subelement_meta = {s["code"]: s for s in self.subelements}
        self.section_order = [s["code"] for s in self.sections]

    def __len__(self):
        return len(self.questions)

    def section_title(self, code):
        return self.section_meta.get(code, {}).get("title", code)

    def subelement_of(self, section):
        return self.section_meta.get(section, {}).get("subelement")

    def figure_url(self, question):
        fig = question.get("figure")
        if not fig:
            return None
        name = self.figures.get(fig)
        return f"/figure/{self.pool_id}/{name}" if name else None

    def figure_highlight(self, question):
        """Where the part a question names sits in its figure, or None.

        "What is component 3 in figure T-2?" names a part, and a room
        identifies it faster with that part ringed and enlarged beside the
        whole figure. "Which symbol represents a Zener diode?" names
        nothing - the answer is a place in the figure - and gets no
        highlight, whatever the map says. The map is the pool's
        highlights.json: a box per numbered part, as fractions of the image.
        """
        import json
        import re
        fig = question.get("figure")
        if not fig:
            return None
        m = re.search(r"component\s+(\d+)", question.get("text") or "", re.IGNORECASE)
        if not m:
            return None
        if not hasattr(self, "_highlights"):
            path = ROOT / "data" / "figures" / self.pool_id / "highlights.json"
            try:
                self._highlights = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._highlights = {}
        box = (self._highlights.get(fig) or {}).get(m.group(1))
        if not box:
            return None
        return {"part": m.group(1), "box": [float(v) for v in box]}


@lru_cache(maxsize=1)
def load_pools():
    pools = {}
    for path in sorted(POOL_DIR.glob("*.json")):
        pool = Pool(json.loads(path.read_text()))
        pools[pool.pool_id] = pool
    return dict(sorted(pools.items(), key=lambda kv: kv[1].order))


def get_pool(pool_id):
    pools = load_pools()
    if pool_id not in pools:
        raise KeyError(pool_id)
    return pools[pool_id]


def presentation(question, rng=None):
    """Shuffle the choices the way a real exam does and report the new key.

    'All these choices are correct' style options are pinned to the end, since
    moving them changes what the question means.
    """
    rng = rng or random
    idx = list(range(len(question["choices"])))
    sticky = [i for i in idx
              if question["choices"][i].strip().lower().rstrip(".") in _STICKY_LAST]
    movable = [i for i in idx if i not in sticky]
    rng.shuffle(movable)
    order = movable + sticky
    return {
        "order": order,
        "choices": [question["choices"][i] for i in order],
        "answer": order.index(question["answer"]),
    }
