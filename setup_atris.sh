#!/usr/bin/env bash
# Configure the current shell for AtRIS.
#
# Usage:
#   source setup_atris.sh
#
# The script finds the AtRIS checkout from its own location, exports ATRIS_ROOT,
# adds the compiled AtRIS executable and user-installed Python commands to PATH,
# and loads the Geant4 environment. It supports Bash and zsh and is expected to
# be sourced so these changes remain in the current shell.
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

# Helper function to print one command string, then execute that same string.
run() {
    echo "$1"
    eval "$1"
}

# Export the checkout path for the Python tools.
run "export ATRIS_ROOT=\"$atris_root\""

# Add the compiled AtRIS executable to PATH.
run 'export PATH="$ATRIS_ROOT/build:$PATH"'

# pip may install commands such as atris-plot for the current user rather than
# system-wide. Ask Python for that user installation location instead of
# assuming it is always $HOME/.local.
python_user_bin="$(python -m site --user-base)/bin"
run "export PATH=\"$python_user_bin:\$PATH\""

# Load the Geant4 environment from the adjacent installation.
run "source \"${geant4_dir[@]}/install/bin/geant4.sh\""

unset atris_root geant4_dir python_user_bin
unset -f run
