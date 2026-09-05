"""Desktop launcher - the menu entry, its icon and the desktop shortcut.

`./elmer.py --install-launcher` puts ELMER in the applications menu with its
own icon, so it can be started by clicking it rather than from a terminal.

The layout is the one the freedesktop spec expects and that the desktop here
already uses: the icon goes into the hicolor theme at several sizes under a
themed name, the menu entry into ~/.local/share/applications, and a small
Type=Link file on the desktop points at that entry rather than duplicating it.

The entry starts ELMER in kiosk mode, since a launcher is for the machine with
the screen attached.  A right-click action opens it in an ordinary window
instead, for when you would rather keep a terminal and other windows around.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "elmer"

# Matching what is already installed here; 512 is for anything hidpi.
ICON_SIZES = (48, 64, 128, 256, 512)


def _home_share():
    """XDG data home, honouring the environment if it is set."""
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")


def _desktop_dir():
    """The user's desktop folder, or None if this desktop has no such thing."""
    directory = Path.home() / "Desktop"
    return directory if directory.is_dir() else None


def _paths():
    share = _home_share()
    return {
        "entry": share / "applications" / f"{APP_ID}.desktop",
        "icons": [share / "icons" / "hicolor" / f"{size}x{size}" / "apps" /
                  f"{APP_ID}.png" for size in ICON_SIZES],
        "shortcut": (_desktop_dir() / f"{APP_ID}.desktop") if _desktop_dir() else None,
    }


def _entry_text(launcher):
    """The .desktop file.  Exec is absolute - a menu entry has no working dir."""
    return f"""[Desktop Entry]
Type=Application
Version=1.0
Name=ELMER
GenericName=Radio Study Assistant
Comment=Study for US amateur and commercial radio licences
Exec={launcher} --kiosk
Path={ROOT}
Icon={APP_ID}
Terminal=false
Categories=Education;HamRadio;
Keywords=ham;radio;amateur;licence;license;exam;propagation;morse;
StartupNotify=true
Actions=Windowed;

[Desktop Action Windowed]
Name=Open in a window
Exec={launcher}
"""


def _shortcut_text(entry):
    return f"""[Desktop Entry]
Type=Link
Name=ELMER
Icon={APP_ID}
URL={entry}
"""


def _refresh(share):
    """Nudge the menu and icon caches.  Missing tools are not an error."""
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(share / "applications")],
                       capture_output=True, check=False)
    if shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-f", "-t",
                        str(share / "icons" / "hicolor")],
                       capture_output=True, check=False)


def install():
    """Install the menu entry, icon and desktop shortcut.  Returns the paths."""
    from PIL import Image

    source = ROOT / "elmer" / "static" / "icon.png"
    if not source.is_file():
        raise FileNotFoundError(
            f"no icon at {source} - drop one in as static/icon.png first")

    icon = Image.open(source).convert("RGBA")
    written = []
    paths = _paths()

    for size, target in zip(ICON_SIZES, paths["icons"]):
        target.parent.mkdir(parents=True, exist_ok=True)
        icon.resize((size, size), Image.LANCZOS).save(target, optimize=True)
        written.append(target)

    launcher = ROOT / "elmer.py"
    entry = paths["entry"]
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(_entry_text(launcher))
    entry.chmod(0o755)
    written.append(entry)

    if paths["shortcut"] is not None:
        paths["shortcut"].write_text(_shortcut_text(entry))
        paths["shortcut"].chmod(0o755)
        written.append(paths["shortcut"])

    _refresh(_home_share())
    log.info("launcher installed: %s", entry)
    return written


def entry_path():
    """Where the menu entry lives."""
    return _paths()["entry"]


def owner():
    """The install directory the menu entry points at, or None if there is none.

    The entry lives in the user's own share directory, not in the install, so
    on a machine with two copies of ELMER there is still only one of it - and
    it belongs to whichever copy wrote it last.
    """
    entry = _paths()["entry"]
    if not entry.is_file():
        return None
    for line in entry.read_text(errors="replace").splitlines():
        if line.startswith("Exec="):
            command = line[len("Exec="):].strip()
            if not command:
                return None
            return Path(command.split()[0]).resolve().parent
    return None


def installed():
    """True if the menu entry is in place, whoever it belongs to."""
    return _paths()["entry"].is_file()


def installed_here():
    """True if the menu entry points at this copy of ELMER."""
    mine = Path(__file__).resolve().parents[1]
    return owner() == mine


def remove(force=False):
    """Take the launcher back out again.  Returns what was actually removed.

    Returns None rather than removing anything when the entry belongs to a
    different copy of ELMER: a second checkout - a clone, a test copy, the one
    somebody is working in - should not be able to take the menu entry away
    from the install that is actually being used.
    """
    if installed() and not installed_here() and not force:
        return None
    paths = _paths()
    removed = []
    for target in paths["icons"] + [paths["entry"], paths["shortcut"]]:
        if target is not None and target.exists():
            target.unlink()
            removed.append(target)
    _refresh(_home_share())
    return removed
