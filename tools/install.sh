#!/bin/sh
# One-shot dependency setup for the ARS plugin.
#
# Creates an isolated venv, installs requirements.txt into it, and verifies the
# imports the helper scripts actually need. bin/python3 then routes the plugin's
# own scripts to that venv and leaves every other python3 call alone.
#
# Usage:
#   sh tools/install.sh                 # default venv: ~/.local/share/ars-venv
#   sh tools/install.sh --venv DIR      # custom location (also records it)
#   sh tools/install.sh --python CMD    # base interpreter to build the venv with
#   sh tools/install.sh --check         # report status only, change nothing
set -eu

PLUGIN_ROOT=$(CDPATH= cd -P -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_VENV="$HOME/.local/share/ars-venv"
VENV_DIR="$DEFAULT_VENV"
BASE_PY="${PYTHON:-python3}"
CHECK_ONLY=0
REQS="$PLUGIN_ROOT/requirements.txt"
# Modules the helper scripts import. Keep in sync with requirements.txt.
NEEDED="yaml jsonschema pypdf ruamel.yaml defusedxml requests"

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --venv)    VENV_DIR=${2:?--venv needs a directory}; shift 2 ;;
        --python)  BASE_PY=${2:?--python needs a command};  shift 2 ;;
        --check)   CHECK_ONLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# A venv's python lives in bin/ on POSIX and Scripts/ on Windows.
venv_python() {
    for p in "$1/bin/python" "$1/bin/python3" "$1/Scripts/python.exe"; do
        [ -x "$p" ] && { printf '%s\n' "$p"; return 0; }
    done
    return 1
}

venv_pip() {
    for p in "$1/bin/pip" "$1/bin/pip3" "$1/Scripts/pip.exe"; do
        [ -x "$p" ] && { printf '%s\n' "$p"; return 0; }
    done
    return 1
}

# Echo the modules from $NEEDED that $1 cannot import (empty output = all good).
missing_deps() {
    "$1" -c '
import importlib.util, sys
print(" ".join(m for m in sys.argv[1].split() if importlib.util.find_spec(m) is None))
' "$NEEDED" 2>/dev/null || printf '%s\n' "$NEEDED"
}

# ------------------------------------------------------------------- report
if [ "$CHECK_ONLY" -eq 1 ]; then
    status=0
    printf 'plugin root : %s\n' "$PLUGIN_ROOT"
    if [ -x "$PLUGIN_ROOT/bin/python3" ]; then
        printf 'router      : present (bin/python3)\n'
    else
        printf 'router      : MISSING (bin/python3 not executable)\n'; status=1
    fi
    if PY=$(venv_python "$VENV_DIR"); then
        printf 'venv        : %s\n' "$PY"
        miss=$(missing_deps "$PY")
        if [ -z "$miss" ]; then
            printf 'deps        : ok\n'
        else
            printf 'deps        : MISSING %s\n' "$miss"
            printf '              run: sh tools/install.sh\n'; status=1
        fi
    else
        printf 'venv        : MISSING at %s\n' "$VENV_DIR"
        printf '              run: sh tools/install.sh\n'; status=1
    fi
    if [ -f "$PLUGIN_ROOT/python-path" ]; then
        printf 'python-path : %s\n' "$(head -n 1 "$PLUGIN_ROOT/python-path")"
    fi
    [ -n "${ARS_PYTHON:-}" ] && printf 'ARS_PYTHON   : %s\n' "$ARS_PYTHON"
    exit "$status"
fi

# -------------------------------------------------------------------- venv
if PY=$(venv_python "$VENV_DIR"); then
    echo "reusing venv: $PY"
else
    echo "creating venv: $VENV_DIR"
    mkdir -p "$(dirname -- "$VENV_DIR")"
    if ! "$BASE_PY" -m venv "$VENV_DIR" 2>/tmp/ars-venv-$$.err; then
        echo "error: could not create a venv with '$BASE_PY'" >&2
        sed 's/^/  /' /tmp/ars-venv-$$.err >&2
        rm -f /tmp/ars-venv-$$.err
        echo "hint: install the venv module, e.g.  apt install python3-venv" >&2
        echo "hint: or point at an existing interpreter:  sh tools/install.sh --venv DIR" >&2
        exit 1
    fi
    rm -f /tmp/ars-venv-$$.err
    PY=$(venv_python "$VENV_DIR") || { echo "error: venv has no python" >&2; exit 1; }
fi

# --------------------------------------------------------------------- deps
if ! PIP=$(venv_pip "$VENV_DIR"); then
    echo "bootstrapping pip in $VENV_DIR"
    "$PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
    PIP=$(venv_pip "$VENV_DIR") || {
        echo "error: no pip in $VENV_DIR" >&2
        exit 1
    }
fi

echo "installing $REQS"
if ! "$PIP" install --disable-pip-version-check -q -r "$REQS"; then
    echo "error: pip install failed" >&2
    echo "hint: retry verbosely with  $PIP install -r $REQS" >&2
    exit 1
fi

# -------------------------------------------------------------------- verify
echo "verifying imports"
miss=$(missing_deps "$PY")
if [ -n "$miss" ]; then
    echo "error: interpreter still cannot import: $miss" >&2
    echo "hint: retry verbosely with  $PY -m pip install -r $REQS" >&2
    exit 1
fi

# A non-default location must be recorded, otherwise bin/python3 won't find it.
if [ "$VENV_DIR" != "$DEFAULT_VENV" ]; then
    printf '%s\n' "$PY" > "$PLUGIN_ROOT/python-path"
    echo "recorded: $PLUGIN_ROOT/python-path"
    echo "note: this file is machine-local; export ARS_PYTHON=$PY instead if you"
    echo "      installed the plugin from git (the pointer does not survive updates)."
fi

echo
echo "done."
echo "  scripts -> $PY"
echo "  next    : start a CodeBuddy session and run /reload-plugins"
