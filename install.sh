#!/usr/bin/env bash
#
# ELMER installer.
#
# Installs what is missing and nothing that is not: it checks first, tells you
# exactly what it intends to do, and only asks for sudo if a system package is
# actually needed. Safe to run more than once.
#
#   ./install.sh                 check, install, offer a menu entry
#   ./install.sh --yes           no questions; assume yes to all of them
#   ./install.sh --venv          use a virtual environment instead of apt
#   ./install.sh --no-launcher   skip the desktop and menu entry
#   ./install.sh --uninstall     remove the menu entry and the virtualenv
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

ASSUME_YES=0
FORCE_VENV=0
WANT_LAUNCHER=1
UNINSTALL=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y)      ASSUME_YES=1 ;;
        --venv)        FORCE_VENV=1 ;;
        --no-launcher) WANT_LAUNCHER=0 ;;
        --uninstall)   UNINSTALL=1 ;;
        --help|-h)     sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

# --------------------------------------------------------------- uninstall
if [ "$UNINSTALL" = 1 ]; then
    head2 "Removing ELMER's menu entry and virtual environment"
    python3 ./elmer.py --remove-launcher 2>/dev/null && ok "menu entry removed" \
        || warn "no menu entry to remove"
    if [ -d .venv ]; then
        rm -rf .venv && ok "virtual environment removed"
    fi
    printf '\n  Your study data in data/ has been left alone.\n'
    printf '  Delete the whole directory to remove ELMER itself.\n\n'
    exit 0
fi

# ------------------------------------------------------------------ python
head2 "ELMER installer"
printf '  %sinstalling into %s%s\n' "$DIM" "$HERE" "$OFF"

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
    if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        warn "no desktop session here, so no menu entry was added"
        printf '  %sRun ./install.sh again from the desktop to add one.%s\n' "$DIM" "$OFF"
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

printf '\n%sReady.%s\n' "$BOLD" "$OFF"
printf '  Start it with        %s./elmer.py%s\n' "$BOLD" "$OFF"
printf '  Full screen with     %s./elmer.py --kiosk%s\n' "$BOLD" "$OFF"
printf '  Check the install    %s./elmer.py --doctor%s\n' "$BOLD" "$OFF"
printf '  Update it later      %s./elmer.py --update%s\n' "$BOLD" "$OFF"
printf '  Remove the entry     %s./install.sh --uninstall%s\n\n' "$BOLD" "$OFF"
