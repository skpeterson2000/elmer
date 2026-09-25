#!/usr/bin/env python3
"""Checks for the first-contact track on Make Contact.

    python3 tests/test_track.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import track as T  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


REPEATER = {"key": "repeater", "rows": [{"call": "W0ABC", "output": 146.94, "offset": -0.6, "tone": "100.0",
                                         "miles": 9, "bearing": 210, "band": "2 m"}]}


def main():
    print("\n-- a new Technician with a handheld --")
    steps = T.build(["ht"], "Technician", [REPEATER], "KC9SP")
    keys = [s["key"] for s in steps]
    check("listen, program, key up, the net, simplex, log, next - in that order",
          keys, ["listen", "program", "key", "net", "simplex", "log", "next"])
    program = steps[1]
    check("the nearest machine is written into the programming step",
          all(w in program["how"] for w in ("W0ABC", "146.940", "-0.6", "100.0", "9 miles")), True)
    check("  and the operator's own call into the words to say", "'KC9SP, monitoring'" in steps[2]["how"], True)
    check("the first undone step is the next one", [s["next"] for s in steps], [True] + [False] * 6)
    check("every step says how you know", all(s["know"] for s in steps), True)

    print("\n-- with two steps done --")
    steps = T.build(["ht"], "Technician", [REPEATER], "KC9SP", {"listen": "2026-09-10", "program": "2026-09-12"})
    check("done steps carry their date", (steps[0]["done"], steps[1]["done"]), ("2026-09-10", "2026-09-12"))
    check("  and the next is the third", next(s["key"] for s in steps if s["next"]), "key")

    print("\n-- no repeater known, no callsign yet --")
    steps = T.build(["ht"], "Technician", [], "")
    check("the words still work without a call", "'your callsign, monitoring'" in steps[2]["how"], True)
    check("  and the programming step points at the list", "in the list below" in steps[1]["how"], True)

    print("\n-- HF adds the wire and answering a CQ --")
    keys = [s["key"] for s in T.build(["ht", "hf_wire"], "General", [REPEATER], "KC9SP")]
    check("antenna and answer come after the VHF steps", keys[5:7], ["antenna", "answer"])
    keys = [s["key"] for s in T.build(["hf_wire"], "General", [], "KC9SP")]
    check("HF alone skips the repeater steps", "program" in keys, False)

    print("\n-- no license --")
    steps = T.build(["ht", "cb"], "none", [REPEATER], "")
    check("listen, a contact that is already allowed, then the exam",
          [s["key"] for s in steps], ["listen", "personal", "exam"])
    check("  the exam step links the pool", steps[-1]["link"], "/study/tech2026")
    steps = T.build(["ht"], "none", [REPEATER], "")
    check("  without a personal radio, listen and the exam", [s["key"] for s in steps], ["listen", "exam"])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
