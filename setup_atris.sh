#!/usr/bin/env bash
# Determine the AtRIS path from this script's location.
# Export ATRIS_ROOT, add the AtRIS executable to PATH, and load Geant4.
# The script can be sourced from Bash or zsh.

if [[ -n "${BASH_VERSION:-}" ]]
then
    _atris_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    _atris_root="$(cd "$(dirname "${(%):-%x}")" && pwd)"
fi

_set_root="export ATRIS_ROOT=\"$_atris_root\""
_set_path='export PATH="$ATRIS_ROOT/atris/build:$PATH"'
_source_geant4='source "$ATRIS_ROOT"/../geant4-*/install/bin/geant4.sh'

echo "$_set_root"
eval "$_set_root"
echo "$_set_path"
eval "$_set_path"
echo "$_source_geant4"
eval "$_source_geant4"

unset _atris_root _set_root _set_path _source_geant4
