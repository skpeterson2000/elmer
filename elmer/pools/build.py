"""Turn the raw pool documents in data/raw into normalized JSON in data/pools.

Both pool families reduce to the same shape: a pool has subelements, each
subelement has *sections*, and a real exam draws exactly one question from
every section.  For the amateur pools a section is an NCVEC "group" (T1A); for
the FCC pools it is a "Key Topic" (3-13).  That single rule reproduces the
published exam blueprint for all five exams.
"""
import json
import re
from datetime import date
from pathlib import Path

from . import figures as figmod
from .parse_fcc import parse as parse_fcc
from .parse_ncvec import parse as parse_ncvec

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "pools"
FIGDIR = ROOT / "data" / "figures"

NCVEC = "https://www.ncvec.org/"
FCC = ("https://www.fcc.gov/wireless/bureau-divisions/mobility-division/"
       "commercial-radio-operator-license-program/examinations")

AMATEUR = [
    {
        "pool_id": "tech2026", "rank_name": "Technician", "name": "Technician",
        "long_name": "Technician Class - FCC Element 2",
        "track": "amateur", "element": 2, "order": 1,
        "file": "tech2026.docx", "exam_questions": 35, "pass_mark": 26,
        "valid_from": "2026-07-01", "valid_to": "2030-06-30",
        "edition": "2026-2030 pool, errata of 19 Feb 2026",
        "source_url": NCVEC,
        "figures": {"kind": "pages", "file": "tech_figures.pdf",
                    "pages": {1: "T-1", 2: "T-2", 3: "T-3"}},
    },
    {
        "pool_id": "gen2023", "rank_name": "General", "name": "General",
        "long_name": "General Class - FCC Element 3",
        "track": "amateur", "element": 3, "order": 2,
        "file": "gen2023.docx", "exam_questions": 35, "pass_mark": 26,
        "valid_from": "2023-07-01", "valid_to": "2027-06-30",
        "edition": "2023-2027 pool, 6th errata of 4 Feb 2026",
        "source_url": NCVEC,
        "figures": {"kind": "pages", "file": "gen_figures.pdf",
                    "pages": {1: "G7-1"}},
    },
    {
        "pool_id": "extra2024", "rank_name": "Amateur Extra", "name": "Amateur Extra",
        "long_name": "Amateur Extra Class - FCC Element 4",
        "track": "amateur", "element": 4, "order": 3,
        "file": "extra2024.docx", "exam_questions": 50, "pass_mark": 37,
        "valid_from": "2024-07-01", "valid_to": "2028-06-30",
        "edition": "2024-2028 pool, 4th errata of 4 Feb 2026",
        "source_url": NCVEC,
        "figures": {"kind": "svgzip", "file": "extra_figures.zip"},
    },
]

COMMERCIAL = [
    {
        "pool_id": "element1", "rank_name": "MROP", "name": "Element 1 (MROP)",
        "long_name": "Marine Radio Operator Permit - FCC Element 1",
        "track": "commercial", "element": 1, "order": 4,
        "file": "element1.pdf", "exam_questions": 24, "pass_mark": 18,
        "edition": "2009 pool, approved 25 June 2009", "source_url": FCC,
        "figures": {"kind": "embedded"},
    },
    {
        "pool_id": "element3", "rank_name": "GROL", "name": "Element 3 (GROL)",
        "long_name": "General Radiotelephone Operator License - FCC Element 3",
        "track": "commercial", "element": 3, "order": 5,
        "file": "element3.pdf", "exam_questions": 100, "pass_mark": 75,
        "edition": "2009 pool, approved 25 June 2009", "source_url": FCC,
        "figures": {"kind": "embedded"},
    },
    {
        "pool_id": "element8", "rank_name": "Ship Radar", "name": "Element 8 (Radar)",
        "long_name": "Ship Radar Endorsement - FCC Element 8",
        "track": "commercial", "element": 8, "order": 6,
        "file": "element8.pdf", "exam_questions": 50, "pass_mark": 38,
        "edition": "2009 pool, updated 6 March 2024", "source_url": FCC,
        "figures": {"kind": "embedded"},
    },
]

RE_TITLE_TAIL = re.compile(r"\s*[-–]\s*\d+\s+Key Topics.*$", re.I)


def _clean(title):
    return RE_TITLE_TAIL.sub("", title).strip(" -–")


def build_amateur(meta):
    questions, subels, groups, deleted = parse_ncvec(RAW / meta["file"])

    # NCVEC prints subelement 0 (safety) last, so follow the syllabus order
    sections = []
    for code in sorted(groups, key=lambda c: (c[1] == "0", c[1], c[2])):
        sections.append({
            "code": code, "title": groups[code], "subelement": code[:2],
            "exam_questions": 1,
        })
    subelements = [
        {"code": c, "title": _clean(subels[c]["title"]),
         "exam_questions": subels[c]["exam_questions"]}
        for c in sorted(subels, key=lambda c: (c[1] == "0", c[1]))
    ]
    order = {code: n for n, code in enumerate(s["code"] for s in sections)}
    out = []
    for qid in sorted(questions, key=lambda k: (order[questions[k]["group"]], k)):
        q = questions[qid]
        out.append({
            "id": qid, "section": q["group"], "subelement": q["subelement"],
            "text": q["text"], "choices": q["choices"], "answer": q["answer"],
            "refs": q["refs"], "figure": q["figure"],
        })
    return sections, subelements, out, sorted(deleted)


def build_commercial(meta):
    questions, subels, topics, unmatched = parse_fcc(RAW / meta["file"],
                                                     meta["element"])
    if unmatched:
        raise SystemExit(f"{meta['pool_id']}: unmatched answer key {unmatched}")

    sections = [
        {"code": f"{meta['element']}-{n}", "title": topics[n]["title"],
         "subelement": topics[n]["subelement"], "exam_questions": 1}
        for n in sorted(topics)
    ]
    subelements = [
        {"code": c, "title": _clean(subels[c]["title"]),
         "exam_questions": sum(1 for s in sections if s["subelement"] == c)}
        for c in sorted(subels)
    ]
    out = []
    for qid in sorted(questions, key=lambda k: (questions[k]["topic"], k)):
        q = questions[qid]
        out.append({
            "id": qid, "section": f"{meta['element']}-{q['topic']}",
            "subelement": q["subelement"], "text": q["text"],
            "choices": q["choices"], "answer": q["answer"],
            "refs": None, "figure": q["figure"],
        })
    return sections, subelements, out, []


def build_figures(meta, questions):
    wanted = {q["figure"] for q in questions if q["figure"]}
    if not wanted:
        return {}
    out_dir = FIGDIR / meta["pool_id"]
    spec = meta["figures"]
    if spec["kind"] == "svgzip":
        return figmod.extract_svg_zip(RAW / spec["file"], out_dir, wanted)
    if spec["kind"] == "pages":
        out_dir.mkdir(parents=True, exist_ok=True)
        return figmod.extract_page_pdf(RAW / spec["file"], out_dir, spec["pages"])
    return figmod.extract_fcc(RAW / meta["file"], out_dir, wanted)


def build_pool(meta):
    if meta["track"] == "amateur":
        sections, subelements, questions, deleted = build_amateur(meta)
    else:
        sections, subelements, questions, deleted = build_commercial(meta)

    figs = build_figures(meta, questions)
    missing = sorted({q["figure"] for q in questions if q["figure"]} - set(figs))

    pool = {
        "pool_id": meta["pool_id"], "name": meta["name"],
        "rank_name": meta["rank_name"],
        "long_name": meta["long_name"], "track": meta["track"],
        "element": meta["element"], "order": meta["order"],
        "exam_questions": meta["exam_questions"], "pass_mark": meta["pass_mark"],
        "valid_from": meta.get("valid_from"), "valid_to": meta.get("valid_to"),
        "edition": meta["edition"],
        "source": {"url": meta["source_url"], "file": meta["file"],
                   "built": date.today().isoformat()},
        "subelements": subelements, "sections": sections,
        "questions": questions, "figures": figs,
        "withdrawn": deleted,
    }
    validate(pool, missing)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{meta['pool_id']}.json").write_text(json.dumps(pool, indent=1))
    return pool, missing


def validate(pool, missing_figs):
    errors = []
    codes = {s["code"] for s in pool["sections"]}
    if len(codes) != pool["exam_questions"]:
        errors.append(f"{len(codes)} sections but exam draws "
                      f"{pool['exam_questions']} questions")
    seen = set()
    for q in pool["questions"]:
        if q["id"] in seen:
            errors.append(f"duplicate id {q['id']}")
        seen.add(q["id"])
        if len(q["choices"]) != 4:
            errors.append(f"{q['id']}: {len(q['choices'])} choices")
        if q["answer"] not in (0, 1, 2, 3):
            errors.append(f"{q['id']}: bad answer {q['answer']!r}")
        if q["section"] not in codes:
            errors.append(f"{q['id']}: unknown section {q['section']}")
        if not q["text"].strip():
            errors.append(f"{q['id']}: empty stem")
        if any(not c.strip() for c in q["choices"]):
            errors.append(f"{q['id']}: empty choice")
    empty = codes - {q["section"] for q in pool["questions"]}
    if empty:
        errors.append(f"sections with no questions: {sorted(empty)}")
    if missing_figs:
        errors.append(f"missing figures: {missing_figs}")
    if errors:
        raise SystemExit(f"{pool['pool_id']} failed validation:\n  "
                         + "\n  ".join(errors))


def build_all(with_rules=True):
    if with_rules:
        from . import rules
        try:
            rules.build(97)
        except Exception as exc:               # offline rebuild is still useful
            print(f"  47 CFR part 97: skipped ({exc})")
    results = []
    for meta in AMATEUR + COMMERCIAL:
        pool, missing = build_pool(meta)
        results.append(pool)
        print(f"  {pool['pool_id']:10s} {len(pool['questions']):4d} questions  "
              f"{len(pool['sections']):3d} sections  "
              f"{len(pool['figures']):2d} figures  "
              f"exam {pool['exam_questions']}/{pool['pass_mark']} to pass")
    total = sum(len(p["questions"]) for p in results)
    print(f"  {'TOTAL':10s} {total:4d} questions")
    return results


if __name__ == "__main__":
    build_all()
