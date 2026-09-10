#!/usr/bin/env python3
"""Where the icons go, and which of them is a choice.

    python3 tests/test_launcher.py

The menu entry is not a choice. It is how somebody who does not use a terminal
finds this program again tomorrow, it costs nothing, it is invisible until
looked for, and one line removes it. The desktop is a choice, because a desktop
is a surface people keep deliberately and an icon put there unasked is a thing
done to somebody's desk.

Run against a temporary home, so a test of where files land never lands any.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import launcher  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


was = {k: os.environ.get(k) for k in ("HOME", "XDG_DATA_HOME")}
home = tempfile.mkdtemp(prefix="elmer-launcher-")
os.environ["HOME"] = home
os.environ["XDG_DATA_HOME"] = str(Path(home) / ".local/share")
(Path(home) / "Desktop").mkdir(parents=True, exist_ok=True)

entry = Path(home) / ".local/share/applications/elmer.desktop"
shortcut = Path(home) / "Desktop/elmer.desktop"

try:
    print("\nby default both, because most people want the desktop one")
    written = launcher.install()
    check("the menu entry is there", entry.is_file(), True)
    check("and so is the desktop one", shortcut.is_file(), True)
    check("the icon in every size", sum(1 for p in written
                                        if p.suffix == ".png"), 5)

    print("\nasked for menu only, the desktop one goes")
    # The answer is about now, not about what was chosen last time - somebody
    # tidying their desk should not have to delete the file by hand.
    launcher.install(desktop=False)
    check("the menu entry stays", entry.is_file(), True)
    check("the desktop one is gone", shortcut.exists(), False)

    print("\nand it can be put back")
    launcher.install(desktop=True)
    check("both again", (entry.is_file(), shortcut.is_file()), (True, True))

    print("\nthe entry starts it full screen, and offers a window as well")
    text = entry.read_text()
    check("kiosk on the main action", "--kiosk" in text, True)
    check("a windowed action too", "[Desktop Action Windowed]" in text, True)
    check("pointed at this copy", str(launcher.ROOT) in text, True)

    print("\nremoving takes the lot")
    launcher.remove(force=True)
    check("no menu entry", entry.exists(), False)
    check("nothing on the desktop", shortcut.exists(), False)

    print("\nwith no desktop folder it installs the menu entry regardless")
    # A headless box, or a desktop that keeps no such folder. The menu entry
    # is the part that must not depend on there being a desk.
    import shutil
    shutil.rmtree(Path(home) / "Desktop")
    launcher.install()
    check("still in the menu", entry.is_file(), True)
    check("and nothing was invented to put it on", shortcut.exists(), False)
finally:
    import shutil
    shutil.rmtree(home, ignore_errors=True)
    for k, v in was.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
