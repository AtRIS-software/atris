#!/usr/bin/env python3
"""Convert a downloaded NASA NRLMSIS table to AtRIS PSF."""

import argparse
from pathlib import Path

from . import simtools


def convert_nrlmsis(input_path):
    """Convert a downloaded NRLMSIS table using the existing AtRIS tools."""
    table = Path(input_path).read_text(encoding="utf-8")
    table = table[table.index("Year Mon Day"):]
    atmosphere = simtools._parse_nrlmsis_output(table)
    simtools.nrml2psf(simtools.nrlm_reformer(atmosphere))
    return Path.cwd() / "simulation.psf"


def main():
    """Run the NRLMSIS-to-PSF command."""
    parser = argparse.ArgumentParser(
        description="Convert a downloaded NASA NRLMSIS table to simulation.psf."
    )
    parser.add_argument("nrlmsis_output", type=Path, help="Downloaded NRLMSIS text file.")
    convert_nrlmsis(parser.parse_args().nrlmsis_output)


if __name__ == "__main__":
    main()
