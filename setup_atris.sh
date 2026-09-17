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

# The default layout has one versioned Geant4 directory beside the AtRIS
# checkout. Change this pattern if the Geant4 source and install are elsewhere.
geant4_dir=("$atris_root"/../geant4-v[0-9][0-9].[0-9].[0-9])
if [[ "${#geant4_dir[@]}" -ne 1 || ! -d "${geant4_dir[@]}" ]]
then
    echo "Expected exactly one geant4-v<version> directory beside AtRIS." >&2
    return 1
fi

# Return an existing directory's physical path without changing this shell's
# working directory.
canonicalise_dir() {
    (cd -P "$1" && pwd -P)
}
geant4_dir=("$(canonicalise_dir "${geant4_dir[@]}")") || return 1

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
if ! command -v atris-version >/dev/null 2>&1
then
    if ! command -v python >/dev/null 2>&1
    then
        echo "atris-version is not on PATH and python is unavailable." >&2
    elif python_user_base="$(python -m site --user-base)" &&
         [[ -n "$python_user_base" ]]
    then
        run "export PATH=\"$python_user_base/bin:\$PATH\""
    else
        echo "Could not determine Python's user command directory." >&2
    fi
fi

# Load the Geant4 environment from the adjacent installation.
run "source \"${geant4_dir[@]}/install/bin/geant4.sh\""

# Check revisions quietly when both the local executable and tools exist.
if [[ -x "$ATRIS_ROOT/build/AtRIS" ]] &&
   command -v atris-version >/dev/null 2>&1
then
    atris-version >/dev/null || echo "Warning: version check failed." >&2
fi

unset atris_root geant4_dir python_user_base
unset -f canonicalise_dir run
