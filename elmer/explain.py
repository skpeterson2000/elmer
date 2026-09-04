"""Assemble the explanation shown for a question.

Explanations come from four sources, in descending order of authority, and the
UI shows whichever exist:

1. **Your own note** - kept separately and always shown, because a correction
   you wrote yourself is the one that sticks.
2. **The FCC rule** - for questions carrying a citation, the actual text of
   47 CFR Part 97. Not a paraphrase, so there is nothing to mistrust.
3. **A question rationale** - hand-authored, for questions where a worked
   reason genuinely teaches something.
4. **A section concept note** - hand-authored per syllabus section, which is
   the efficient unit: pool questions cluster hard by concept, so one good
   note covers ten to fifteen questions.

Everything below the user's own note is data on disk, so coverage can grow
without touching code.
"""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "data" / "notes"
RATIONALE_DIR = ROOT / "data" / "explanations"
RULES_DIR = ROOT / "data" / "rules"

# Concept notes may point at a Lab tab that makes the idea interactive.
LAB_TABS = {"skip", "ohm", "react", "swr", "ant", "db", "path"}


@lru_cache(maxsize=None)
def _load(path):
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except ValueError:
        return {}


def section_notes(pool_id):
    return _load(NOTES_DIR / f"{pool_id}.json")


def rationales(pool_id):
    return _load(RATIONALE_DIR / f"{pool_id}.json")


def part97():
    return _load(RULES_DIR / "part97.json")


def rule_text(refs):
    """Render the cited rule, e.g. '97.301(d), 97.305' -> list of blocks."""
    if not refs:
        return []
    from .pools.rules import paragraph_for

    sections = part97()
    out = []
    for citation in [c.strip() for c in refs.split(",") if c.strip()]:
        number = citation.split("(")[0].strip()
        section = sections.get(number)
        if not section:
            continue
        blocks = paragraph_for(section, citation)
        out.append({
            "citation": f"§ {citation}",
            "title": section["title"],
            "blocks": blocks[:14],
            "truncated": len(blocks) > 14,
            "url": f"https://www.ecfr.gov/current/title-47/part-97/section-{number}",
        })
    return out


def for_question(pool, question, user_note=None):
    """Everything ELMER can say about one question, ready to render."""
    section_code = question["section"]
    note = section_notes(pool.pool_id).get(section_code)
    rationale = rationales(pool.pool_id).get(question["id"])
    subelement = pool.subelement_meta.get(question["subelement"], {})

    payload = {
        "question_id": question["id"],
        "section": section_code,
        "section_title": pool.section_title(section_code),
        "subelement": question["subelement"],
        "subelement_title": subelement.get("title"),
        "user_note": user_note,
        "why": (rationale or {}).get("why"),
        "watch_out": (rationale or {}).get("watch_out"),
        "concept": None,
        "rules": rule_text(question.get("refs")),
    }
    if note:
        payload["concept"] = {
            "note": note.get("note"),
            "key_facts": note.get("key_facts", []),
            "lab": note.get("lab") if note.get("lab") in LAB_TABS else None,
        }
    payload["has_content"] = bool(
        payload["why"] or payload["concept"] or payload["rules"] or user_note)
    return payload


def coverage(pool):
    """How much of a pool currently has an explanation, for the doctor."""
    notes = section_notes(pool.pool_id)
    reasons = rationales(pool.pool_id)
    explained = sum(
        1 for q in pool.questions
        if q["id"] in reasons or q["section"] in notes or
        (q.get("refs") and rule_text(q["refs"])))
    return {
        "pool_id": pool.pool_id,
        "questions": len(pool.questions),
        "explained": explained,
        "sections": len(pool.sections),
        "sections_with_notes": sum(1 for s in pool.section_order if s in notes),
        "rationales": len(reasons),
    }
