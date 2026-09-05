#!/usr/bin/env bash
#
# ELMER installer, and the way back to an install that already exists.
#
# Run on a machine with no ELMER on it, it installs what is missing and nothing
# that is not: it checks first, says exactly what it intends to do, and asks for
# sudo only if a system package is genuinely needed.
#
# Run on a machine that already has one, it asks what you came for instead of
# quietly doing an install again - update, repair, remove, or just look.
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

usage() {
    cat <<'USAGE'
ELMER installer

  ./install.sh                 install, or ask what to do if already installed
  ./install.sh --update        fetch and apply the latest ELMER
  ./install.sh --repair        put back what is missing or changed, and re-check
  ./install.sh --check         run the self-check and change nothing
  ./install.sh --remove        take away the menu entry and the virtualenv
                               (--uninstall means the same thing)

  ./install.sh --yes           no questions; assume yes to all of them
  ./install.sh --venv          use a virtual environment instead of apt
  ./install.sh --no-launcher   skip the desktop and menu entry
  ./install.sh --discard-local-changes
                               with --repair, put modified tracked files back
                               as the repository has them. This throws those
                               edits away, so it is never assumed.

Your study data in data/ is never touched by any of these.
USAGE
}

ASSUME_YES=0
FORCE_VENV=0
WANT_LAUNCHER=1
DISCARD=0
MODE=""                       # update | repair | check | remove | install

for arg in "$@"; do
    case "$arg" in
        --yes|-y)      ASSUME_YES=1 ;;
        --venv)        FORCE_VENV=1 ;;
        --no-launcher) WANT_LAUNCHER=0 ;;
        --update)      MODE=update ;;
        --repair)      MODE=repair ;;
        --check)       MODE=check ;;
        --remove|--uninstall) MODE=remove ;;
        --discard-local-changes) DISCARD=1 ;;
        --help|-h)     usage; exit 0 ;;
        *)             echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

if [ -t 1 ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'
    AMBER=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
else
    BOLD=""; DIM=""; GREEN=""; AMBER=""; RED=""; OFF=""
fi
ok()   { printf '  [ %sok%s ]  %s\n'   "$GREEN" "$OFF" "$*"; }
miss() { printf '  [%smiss%s]  %s\n'   "$AMBER" "$OFF" "$*"; }
warn() { printf '  [%swarn%s]  %s\n'   "$AMBER" "$OFF" "$*"; }
bad()  { printf '  [%sFAIL%s]  %s\n'   "$RED"   "$OFF" "$*"; }
head2(){ printf '\n%s%s%s\n' "$BOLD" "$*" "$OFF"; }

ask() {
    # ask "question" -> 0 for yes
    [ "$ASSUME_YES" = 1 ] && return 0
    [ -t 0 ] || return 1                     # not a terminal: do not assume
    local reply
    read -r -p "  $1 [Y/n] " reply || return 1
    case "${reply:-y}" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

# A question whose answer throws something away. Deliberately not routed
# through ask(): --yes means "do not pester me", it does not mean "and you may
# delete my work while you are at it".
confirm_destructive() {
    [ "$DISCARD" = 1 ] && return 0
    [ -t 0 ] || return 1
    local reply
    read -r -p "  $1 [y/N] " reply || return 1
    case "$reply" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

do_remove() {
    head2 "Removing ELMER's menu entry and virtual environment"
    "$PY" ./elmer.py --remove-launcher 2>/dev/null && ok "menu entry removed" \
        || warn "no menu entry to remove"
    if [ -d .venv ]; then
        rm -rf .venv && ok "virtual environment removed"
    fi
    printf '\n  Your study data in data/ has been left alone.\n'
    printf '  Delete the whole directory to remove ELMER itself.\n\n'
}

do_update() {
    head2 "Updating ELMER"
    if [ "$ASSUME_YES" = 1 ]; then
        "$PY" ./elmer.py --update --yes || return 1
    else
        "$PY" ./elmer.py --update || return 1
    fi
    head2 "Checking the install"
    "$PY" ./elmer.py --doctor || true
}

# Tracked files that have drifted from the repository are the one thing that
# stops an install updating, and putting them back is the whole of "repair" for
# a checkout. Untracked files are left alone: they are nobody's business but
# their owner's.
repair_tracked_files() {
    git rev-parse --git-dir >/dev/null 2>&1 || {
        warn "not a git checkout, so there is nothing to compare against"
        printf '  %sRun ./elmer.py --adopt to give this copy a history.%s\n' \
            "$DIM" "$OFF"
        return 0
    }
    local changed
    changed="$(git status --porcelain --untracked-files=no || true)"
    if [ -z "$changed" ]; then
        ok "no local changes - this install matches the repository"
        return 0
    fi
    head2 "Local changes"
    printf '  These tracked files differ from the repository:\n\n'
    printf '%s\n' "$changed" | sed 's/^/      /'
    printf '\n  Putting them back is what lets a drifted install update again.\n'
    printf '  %sThat throws those edits away and cannot be undone.%s\n' "$AMBER" "$OFF"
    if confirm_destructive "Put these files back as the repository has them?"; then
        git checkout -- . && ok "restored from the repository"
    else
        warn "left alone - updates will stay blocked while they differ"
    fi
}

# --------------------------------------------------------------------- python
head2 "ELMER installer"
printf '  %s%s%s\n' "$DIM" "$HERE" "$OFF"

head2 "Python"
PY=python3
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
    ok "using the existing virtual environment at .venv"
fi
if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
    bad "python3 is not installed. Install it and run this again."
    exit 1
fi
PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    ok "python $PYVER"
else
    bad "python $PYVER is too old; ELMER needs 3.9 or newer"
    exit 1
fi

# ------------------------------------------------- is there one here already?
# Any of these means somebody has run ELMER on this machine before, so running
# the installer again is far more likely to be a question than a first install.
installed_signs() {
    local signs=()
    [ -f data/elmer.db ] && signs+=("study data")
    [ -d .venv ] && signs+=("virtual environment")
    "$PY" -c 'from elmer import launcher; raise SystemExit(0 if launcher.installed() else 1)' \
        2>/dev/null && signs+=("menu entry")
    # Joined by hand: IFS uses only its first character, so "', '" would put
    # the comma in and leave the space out.
    local out=""
    local sign
    for sign in ${signs[@]+"${signs[@]}"}; do out="${out:+$out, }$sign"; done
    printf '%s' "$out"
}

SIGNS="$(installed_signs || true)"

if [ -z "$MODE" ] && [ -n "$SIGNS" ] && [ -t 0 ] && [ "$ASSUME_YES" = 0 ]; then
    head2 "ELMER is already installed here"
    printf '  %sfound: %s%s\n\n' "$DIM" "$SIGNS" "$OFF"
    printf '    1) Update    fetch the latest ELMER and apply it\n'
    printf '    2) Repair    put back anything missing or changed, and re-check\n'
    printf '    3) Remove    take away the menu entry and the virtualenv\n'
    printf '    4) Check     run the self-check and change nothing\n'
    printf '    5) Quit\n\n'
    printf '  %sYour study data in data/ is left alone by all of these.%s\n\n' \
        "$DIM" "$OFF"
    read -r -p "  Which? [1-5, default 4] " choice || choice=5
    case "${choice:-4}" in
        1) MODE=update ;;
        2) MODE=repair ;;
        3) MODE=remove ;;
        4) MODE=check ;;
        5|q|Q) printf '\n  Nothing done.\n\n'; exit 0 ;;
        *) printf '\n  Not one of the options, so nothing done.\n\n'; exit 2 ;;
    esac
fi

[ -z "$MODE" ] && MODE=install

case "$MODE" in
    remove) do_remove; exit 0 ;;
    update) do_update; exit $? ;;
    check)  head2 "Checking the install"; "$PY" ./elmer.py --doctor; exit $? ;;
esac

# From here on it is an install or a repair, which are the same walk: check
# what is here, put back what is not.
if [ "$MODE" = repair ]; then
    head2 "Repairing"
    repair_tracked_files
fi

# ------------------------------------------------------------ what is missing
head2 "Checking what is already here"

declare -a MISSING_PY=() MISSING_APT=() MISSING_OPT=()

check_py() {                                  # check_py <import> <apt> <pip>
    if "$PY" -c "import $1" >/dev/null 2>&1; then
        ok "$1"
    else
        miss "$1"
        MISSING_PY+=("$3")
        MISSING_APT+=("$2")
    fi
}
check_bin() {                                 # check_bin <binary> <apt> <why>
    if command -v "$1" >/dev/null 2>&1; then
        ok "$1"
    else
        miss "$1 — $3"
        MISSING_APT+=("$2")
    fi
}
check_optional() {                            # check_optional <binary> <apt> <why>
    if command -v "$1" >/dev/null 2>&1; then
        ok "$1"
    else
        warn "$1 not found — $3"
        MISSING_OPT+=("$2")
    fi
}

check_py flask python3-flask "Flask>=2.2"
check_py PIL python3-pil "Pillow>=9.0"
check_py reportlab python3-reportlab "reportlab>=3.6"
check_bin pdftotext poppler-utils "needed to build the question pools"
check_bin pdftoppm poppler-utils "needed to build the question pools"
check_bin pdfimages poppler-utils "needed to build the question pools"
check_bin ss iproute2 "used to spot an ELMER already running"
check_optional zenity zenity "kiosk mode cannot ask questions without it"
if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 \
   || command -v firefox >/dev/null 2>&1; then
    ok "a browser for kiosk mode"
else
    warn "no chromium or firefox — kiosk mode will not start"
    MISSING_OPT+=(chromium)
fi

# dedupe, preserving order
dedupe() { printf '%s\n' "$@" | awk 'NF && !seen[$0]++'; }

# --------------------------------------------------------------- installing
NEED_APT=()
if [ ${#MISSING_APT[@]} -gt 0 ]; then
    mapfile -t NEED_APT < <(dedupe "${MISSING_APT[@]}")
fi
NEED_OPT=()
if [ ${#MISSING_OPT[@]} -gt 0 ]; then
    mapfile -t NEED_OPT < <(dedupe "${MISSING_OPT[@]}")
fi

USE_VENV=$FORCE_VENV
if [ "$FORCE_VENV" = 0 ] && [ ${#NEED_APT[@]} -gt 0 ]; then
    if command -v apt-get >/dev/null 2>&1; then
        head2 "System packages needed"
        printf '  %s\n' "${NEED_APT[@]}"
        [ ${#NEED_OPT[@]} -gt 0 ] && printf '  %s(optional: %s)%s\n' \
            "$DIM" "${NEED_OPT[*]}" "$OFF"
        if ask "Install these with apt? (needs sudo)"; then
            ALL=("${NEED_APT[@]}")
            [ ${#NEED_OPT[@]} -gt 0 ] && ALL+=("${NEED_OPT[@]}")
            sudo apt-get update -qq
            sudo apt-get install -y "${ALL[@]}"
            ok "system packages installed"
        else
            USE_VENV=1
        fi
    else
        warn "no apt here, so Python packages go in a virtual environment"
        USE_VENV=1
    fi
fi

if [ "$USE_VENV" = 1 ]; then
    head2 "Virtual environment"
    # --system-site-packages so anything already installed system-wide is reused
    [ -d .venv ] || "$PY" -m venv --system-site-packages .venv
    PY=.venv/bin/python
    # pip reports parse errors for unrelated system packages when the venv can
    # see them. Those are not ours to fix and reading like an install failure is
    # worse than not mentioning them.
    "$PY" -m pip install --quiet --upgrade pip 2>&1 \
        | grep -v 'Error parsing dependencies of' || true
    "$PY" -m pip install --quiet -r requirements.txt 2>&1 \
        | grep -v 'Error parsing dependencies of' || true
    "$PY" - <<'EOF' || { bad "python packages did not install"; exit 1; }
import flask, PIL, reportlab            # noqa: F401  - presence is the test
EOF
    ok "python packages installed into .venv"
    warn "start ELMER with .venv/bin/python elmer.py, or let the menu entry do it"
fi

# ------------------------------------------------------------- question pools
head2 "Question pools"
if ls data/pools/*.json >/dev/null 2>&1; then
    COUNT="$("$PY" - <<'EOF'
import glob, json
print(sum(len(json.load(open(f))["questions"]) for f in glob.glob("data/pools/*.json")))
EOF
)"
    ok "$COUNT questions already built"
else
    if command -v pdftotext >/dev/null 2>&1; then
        printf '  building from data/raw ...\n'
        "$PY" ./elmer.py --build
    else
        bad "cannot build the pools without poppler-utils"
        exit 1
    fi
fi

# ------------------------------------------------------------------ launcher
if [ "$WANT_LAUNCHER" = 1 ]; then
    head2 "Menu entry"
    HAVE_ENTRY=0
    "$PY" -c 'from elmer import launcher; raise SystemExit(0 if launcher.installed() else 1)' \
        2>/dev/null && HAVE_ENTRY=1
    if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        warn "no desktop session here, so no menu entry was added"
        printf '  %sRun ./install.sh again from the desktop to add one.%s\n' "$DIM" "$OFF"
    elif [ "$MODE" = repair ] && [ "$HAVE_ENTRY" = 1 ]; then
        # A repair puts the entry back as it should be without asking: it is
        # already there, and rewriting it is the repair.
        "$PY" ./elmer.py --log-level WARNING --install-launcher
    elif ask "Add ELMER to the applications menu and the desktop?"; then
        # --log-level WARNING keeps the launcher's own log line out of the
        # installer's output; a new user should not be reading log formatting.
        "$PY" ./elmer.py --log-level WARNING --install-launcher
    else
        printf '  %sskipped — add it later with ./elmer.py --install-launcher%s\n' \
            "$DIM" "$OFF"
    fi
fi

# -------------------------------------------------------------------- finish
head2 "Checking the install"
"$PY" ./elmer.py --doctor || true

if [ "$MODE" = repair ]; then
    printf '\n%sRepaired.%s\n' "$BOLD" "$OFF"
else
    printf '\n%sReady.%s\n' "$BOLD" "$OFF"
fi
printf '  Start it with        %s./elmer.py%s\n' "$BOLD" "$OFF"
printf '  Full screen with     %s./elmer.py --kiosk%s\n' "$BOLD" "$OFF"
printf '  Check the install    %s./elmer.py --doctor%s\n' "$BOLD" "$OFF"
printf '  Update it later      %s./elmer.py --update%s\n' "$BOLD" "$OFF"
printf '  Update, repair or remove\n'
printf '                       %s./install.sh%s  %s(it asks)%s\n\n' \
    "$BOLD" "$OFF" "$DIM" "$OFF"
