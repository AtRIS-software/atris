#!/usr/bin/env bash
# Configure the current shell for AtRIS.
#
# Usage:
#   source setup_atris.sh
#
# The script finds the AtRIS checkout from its own location, exports ATRIS_ROOT,
# adds the compiled AtRIS executable to PATH, optionally adds Python's user
# command directory, and loads the Geant4 environment. When both AtRIS and its
# Python tools are installed, it warns if their versions differ. It supports
# Bash and zsh and should be sourced so changes remain in the current shell.
#
# By default, exactly one geant4-vX.Y.Z directory is expected beside the AtRIS
# checkout, with Geant4 installed below it in install/. Change the geant4_dir
# glob below if Geant4 uses a different layout.

# Find the AtRIS checkout from this file, not from the shell's current directory.
if [[ -n "${BASH_VERSION:-}" ]]
then
    atris_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    atris_root="$(cd "$(dirname "${(%):-%x}")" && pwd)"
fi

# Keep a Geant4 environment that has already been loaded. Otherwise, locate
# the sibling from the logical AtRIS path. Computing the parent as text
# preserves layouts where AtRIS and Geant4 are sibling symlinks whose targets
# live in different directories.
geant4_setup=
if [[ ! -d "${GEANT4_DATA_DIR:-}" && ! -d "${G4LEDATA:-}" ]]
then
    atris_parent="$(dirname "$atris_root")"
    geant4_dir=("$atris_parent"/geant4-v[0-9][0-9].[0-9].[0-9])
    if [[ "${#geant4_dir[@]}" -ne 1 || ! -d "${geant4_dir[@]}" ]]
    then
        echo "Expected exactly one geant4-v<version> directory beside AtRIS." >&2
        return 1
    fi
    geant4_setup="${geant4_dir[@]}/install/bin/geant4.sh"
fi

# Helper function to print one command string, then execute that same string.
run() {
    echo "$1"
    eval "$1"
}

# Export the checkout path for the Python tools.
run "export ATRIS_ROOT=\"$atris_root\""

# Add the compiled AtRIS executable to PATH.
run 'export PATH="$ATRIS_ROOT/build:$PATH"'

# Keep commands from the active Python environment. If none is on PATH, make
# commands from a per-user pip installation available without assuming ~/.local.
if ! command -v atris-run >/dev/null 2>&1
then
    if ! command -v python >/dev/null 2>&1
    then
        echo "AtRIS Python tools are not on PATH and python is unavailable." >&2
    elif python_user_base="$(python -m site --user-base)" &&
         [[ -n "$python_user_base" ]]
    then
        run "export PATH=\"$python_user_base/bin:\$PATH\""
    else
        echo "Could not determine Python's user command directory." >&2
    fi
fi

# Load Geant4 from the adjacent installation unless it was already available.
if [[ -n "$geant4_setup" ]]
then
    run "source \"$geant4_setup\""
fi

# Check revisions quietly when both the local executable and tools exist.
if [[ -x "$ATRIS_ROOT/build/AtRIS" ]] &&
   command -v atris-run >/dev/null 2>&1
then
    atris-run --version >/dev/null || echo "Warning: version check failed." >&2
fi

unset atris_root atris_parent geant4_dir geant4_setup python_user_base
unset -f run
