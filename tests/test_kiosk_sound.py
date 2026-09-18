#!/usr/bin/env python3
"""The appliance is allowed to make a sound before anybody has touched it.

    python3 tests/test_kiosk_sound.py

A browser keeps audio silent until a page has been clicked. That is the
right default for the web and the wrong one for an appliance: the opening
announcement is the unit saying it is awake, and a unit that will only say
so once somebody touches it has not told anybody anything. The symptom is
peculiar enough to be worth naming - the announcement arrives minutes late,
on whatever button the operator happens to press first.

Chromium is told with a flag and Firefox with a preference, and the
preference goes in the kiosk's own profile, which is ELMER's and nobody
else's: nothing here changes how the operator's own browser behaves.

This is only the kiosk. Where ELMER opens the page in whatever browser the
machine already has - Windows, and `--serve` anywhere - there is no command
line to put this on, the announcement waits for the first press, and that is
the browser's rule and not ELMER's to override.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import kiosk  # noqa: E402

FAILS = []
FLAG = "--autoplay-policy=no-user-gesture-required"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\n-- the kiosk window --")
command = kiosk._command("/usr/bin/chromium", "chromium", "http://127.0.0.1:5000/",
                         Path("/tmp/profile"))
check("chromium is told the appliance may sound without being clicked",
      FLAG in command, True)
check("  and it is still the kiosk window it always was",
      ("--kiosk" in command, "http://127.0.0.1:5000/" in command), (True, True))

print("\n-- firefox says it with a preference --")
profile = Path(tempfile.mkdtemp(prefix="elmer-kiosk-test-"))
kiosk._allow_sound(profile)
prefs = (profile / "user.js").read_text(encoding="utf-8")
check("the autoplay block is lifted", 'user_pref("media.autoplay.default", 0);' in prefs, True)
check("  including the one that outranks it",
      'user_pref("media.autoplay.blocking_policy", 0);' in prefs, True)

print("\n-- and only in ELMER's own profile --")
# The whole reason a preference file is safe to write: the kiosk profile is
# made by ELMER, under ELMER's state directory, and is not the profile the
# operator browses the web with.
check("the kiosk profile lives under ELMER's own state",
      str(kiosk.PROFILE_DIR).startswith(str(Path(kiosk.paths.STATE))), True)
# A profile it cannot write to is a slower start, not a failure: the
# announcement waits for a press, exactly as it does on a desktop.
kiosk._allow_sound(Path("/definitely/not/a/directory/here"))
check("a profile that cannot be written is not fatal", True, True)

# The window ELMER opens for the FCC or eCFR is a browser window for reading
# somebody else's site. It has no reason to play anything, and is not given
# permission to.
web = kiosk._window_command("/usr/bin/chromium", "chromium", "https://example.gov/",
                            Path("/tmp/profile-web"))
check("the window for an outside site is given no such permission",
      FLAG in web, False)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
