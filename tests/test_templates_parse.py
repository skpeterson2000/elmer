#!/usr/bin/env python3
"""Every inline script in every template balances its brackets.

    python3 tests/test_templates_parse.py

A stray "});" left behind by an edit made the whole inline script of two
pages fail to parse, and it was pushed: net control and the table screen ran
with no script at all, and the only reason anything worked was that one
button's code lived in a separate file. Nothing in the suite read the pages'
JavaScript, so nothing noticed.

This is not a JavaScript parser. It walks each inline script tracking
strings, template literals, comments and bracket depth, and fails on an
unmatched bracket or one left open at the end - which is exactly the class of
fault an edit leaves behind, and the one that took two pages down.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def unmatched(src):
    """The first unmatched bracket as (char, line), or what is left open."""
    stack, i, line, n = [], 0, 1, len(src)
    while i < n:
        c, nxt = src[i], src[i + 1] if i + 1 < n else ""
        if c == "\n":
            line += 1
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                if src[j] == "\n":
                    break               # an unterminated string: let it fall out
                j += 1
            i = j + 1
            continue
        if c == "`":
            j, depth = i + 1, 0
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "$" and src[j + 1:j + 2] == "{":
                    depth += 1
                    j += 2
                    continue
                if src[j] == "}" and depth:
                    depth -= 1
                    j += 1
                    continue
                if src[j] == "`" and depth == 0:
                    break
                if src[j] == "\n":
                    line += 1
                j += 1
            i = j + 1
            continue
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt != "*":
            # A regex literal, by the usual rule: a slash where a value is
            # expected - after an operator, a bracket, a comma or a keyword -
            # rather than after a value, where it would be division.
            k = i - 1
            while k >= 0 and src[k] in " \t":
                k -= 1
            before = src[k] if k >= 0 else "("
            word = re.search(r"([A-Za-z_$][\w$]*)\s*$", src[max(0, k - 12):k + 1])
            starts = (before in "(,=:[!&|?{};+-*%<>~^" or k < 0
                      or (word and word.group(1) in ("return", "typeof", "case", "in", "of")))
            if starts:
                j, in_class = i + 1, False
                while j < n and (src[j] != "/" or in_class):
                    if src[j] == "\\":
                        j += 1
                    elif src[j] == "[":
                        in_class = True
                    elif src[j] == "]":
                        in_class = False
                    elif src[j] == "\n":
                        break
                    j += 1
                i = j + 1
                continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                return ("/*", line)
            line += src[i:j].count("\n")
            i = j + 2
            continue
        if c in "({[":
            stack.append((c, line))
        elif c in ")}]":
            if not stack:
                return (c, line)
            opened, _ = stack.pop()
            if "({[".index(opened) != ")}]".index(c):
                return (c, line)
        i += 1
    return stack[-1] if stack else None


print("\nevery inline script balances")
for path in sorted((ROOT / "elmer" / "templates").glob("*.html")):
    html = path.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    for k, src in enumerate(scripts):
        # Jinja gets its say first, where it can: {{ }} and {% %} never
        # appear inside these scripts, and {# #} comments are stripped.
        src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
        check(f"{path.name} script {k + 1}", unmatched(src), None)

print("\nand so does every static script")
for path in sorted((ROOT / "elmer" / "static").glob("*.js")):
    check(path.name, unmatched(path.read_text(encoding="utf-8")), None)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
