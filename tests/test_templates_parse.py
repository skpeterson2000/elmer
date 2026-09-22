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
sys.path.insert(0, str(Path(__file__).resolve().parent))   # for _browser
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def unmatched(src):
    """The first unmatched bracket as (char, line), or what is left open.

    A template literal is not scanned as one lump any more. It used to be:
    the scanner ran from the opening backtick to the closing one, counting
    `${` as a level down and *any* `}` as a level back up. That is wrong the
    moment an expression inside a literal contains a brace of its own -
    ``${Object.values(gf.balls || {})}`` closed the expression on the `{}`'s
    own brace, and everything after it was read in the wrong mode: real code
    taken for literal text, closing tags like `</h3>` taken for regexes, and
    eventually a perfectly matched `}` reported as unmatched. party_player.html
    was failing on exactly that while the browser compiled it without
    complaint, which is the tell - the two passes below disagreeing means the
    walker is wrong, not the page.

    So the two modes are tracked properly instead. In *text* mode only `${`
    and the closing backtick mean anything; `${` pushes a marker and returns
    to *code* mode, where strings, comments, regexes, nested template
    literals and ordinary brackets all work as they do anywhere else, and the
    `}` that pops the marker goes back into text. Nesting falls out of the
    stack, which is what a stack is for.
    """
    stack, i, line, n = [], 0, 1, len(src)
    text = False                    # inside a template literal's text, not its code
    while i < n:
        c, nxt = src[i], src[i + 1] if i + 1 < n else ""
        if c == "\n":
            line += 1

        if text:
            if c == "\\":           # an escape, including a line continuation
                line += src[i + 1:i + 2] == "\n"
                i += 2
                continue
            if c == "$" and nxt == "{":
                stack.append(("${", line))
                text = False
                i += 2
                continue
            if c == "`":
                stack.pop()         # the backtick that opened this literal
                # Back to code, always: a literal only ever sits in code
                # position, so one nested inside another is nested inside
                # that one's `${ }` and returns to it.
                text = False
                i += 1
                continue
            i += 1
            continue

        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                if j < n and src[j] == "\n":
                    break           # an unterminated string: let it fall out
                j += 1
            i = j + 1
            continue
        if c == "`":
            stack.append(("`", line))
            text = True
            i += 1
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
            if opened == "${":
                # The brace that ends a template expression. Anything else
                # closing here is a bracket opened outside the literal and
                # closed inside it, which is not something that parses.
                if c != "}":
                    return (c, line)
                text = True
                i += 1
                continue
            if opened == "`":
                return (c, line)    # a bracket closed across a template literal
            if "({[".index(opened) != ")}]".index(c):
                return (c, line)
        i += 1
    return stack[-1] if stack else None


# The walker itself, first. It had no test of its own, which is how it came
# to call a good page broken for two days: it reported an unmatched brace in
# party_player.html on a line that reads `} catch (err) {`, and the only
# reason anybody knew better was the browser pass below compiling the same
# script without complaint. A checker nobody checks is a checker that gets
# believed when it is wrong, so the constructs that actually fooled it are
# pinned here alongside the faults it exists to find.
print("\nthe walker knows a balanced script from a broken one")

GOOD = [
    ("a plain object", "const a = {b: 1};"),
    ("a template literal", "const s = `plain text`;"),
    # The one that broke it: a brace inside a template expression.
    ("an object literal inside a template expression",
     "const s = `x${Object.values(o || {}).length}y`;"),
    ("a template literal nested in its own expression",
     "const s = `a${xs.map(x => `<b>${x}</b>`).join('')}b`;"),
    ("a closing brace inside a string inside an expression",
     "const s = `a${f('}')}b`;"),
    ("a closing tag inside a template literal",
     "const s = `<h3>the card</h3>${board(g)}`;"),
    ("a ternary inside an expression",
     "const s = `${g.over ? `<p>${name(g)}</p>` : clubs(g)}`;"),
    ("a regex with a count in it", "const r = /\\d{3}/;"),
    ("division that is not a regex", "const x = (a) / 2 / 3;"),
    ("a brace in a line comment", "// }\nconst a = 1;"),
    ("a brace in a block comment", "/* } */ const a = 1;"),
    ("an apostrophe in a line comment", "// don't\nconst a = {b: 1};"),
    ("a brace in a string", "const a = '}';"),
]
for label, src in GOOD:
    check("  " + label, unmatched(src), None)

BAD = [
    ("a bracket left open", "function f() { return 1;", "{"),
    ("one closing brace too many", "const a = {b: 1}};", "}"),
    # The fault this whole file was written for: a "});" left behind by an
    # edit. The brace is what is reported, being the first thing with
    # nothing open to match it.
    ("a stray close from a bad edit", "poll();\n});", "}"),
    ("the wrong closer", "const a = [1, 2};", "}"),
    ("a brace left open inside a template expression",
     "const s = `a${ f({ b: 1 ) }`;", ")"),
]
for label, src, want in BAD:
    got = unmatched(src)
    check("  " + label, got[0] if got else None, want)


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

# The brackets balancing is not the same as the script parsing. A variable
# declared twice in one block, a stray token, a template literal's ${}
# holding something that is not an expression - the browser refuses the
# whole script and the page runs with none, which is how the table screen
# went blank on 2026-09-15 with every bracket matched. Where a browser is
# on the machine, every script is handed to it to compile, Jinja's own
# tags stood in for by a plain value.
print("\nand a browser compiles every one of them")
try:
    import json
    import _browser
    have_browser = _browser.available()
except Exception:
    have_browser = None
if not have_browser:
    print("  (no browser on this machine - skipped)")
else:
    bundle = []
    for path in sorted((ROOT / "elmer" / "templates").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        for k, src in enumerate(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)):
            src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
            src = re.sub(r"\{%.*?%\}", "", src, flags=re.S)
            src = re.sub(r"\{\{.*?\}\}", "0", src, flags=re.S)
            bundle.append((f"{path.name} script {k + 1}", src))
    for path in sorted((ROOT / "elmer" / "static").glob("*.js")):
        bundle.append((path.name, path.read_text(encoding="utf-8")))
    js = ("(() => { const out = {}; for (const [name, src] of " + json.dumps(bundle) +
          ") { try { new Function(src); out[name] = null; } catch (e) { out[name] = String(e.message); } } "
          "return JSON.stringify(out); })()")
    got = _browser.evaluate("about:blank", js, settle=0.5)
    try:
        results = json.loads(got)
    except (TypeError, ValueError):
        results = {"the browser answered": str(got)[:120]}
    for name, err in results.items():
        check(name, err, None)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
