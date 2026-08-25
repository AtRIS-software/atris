#!/usr/bin/env python3
"""Post-process AtRIS CSV output and create response plots."""

import argparse
import os
from pathlib import Path


os.environ.setdefault("MPLBACKEND", "Agg")

from . import simtools


def main():
    parser = argparse.ArgumentParser(
        description="Post-process AtRIS output and create PDF plots."
    )
    parser.add_argument("run_directory", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "simulations",
        nargs="*",
        default=("protons", "alphas"),
        help="Simulation prefixes to process.",
    )
    args = parser.parse_args()

    run_directory = args.run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise SystemExit("Run directory does not exist: " + str(run_directory))

    previous_directory = Path.cwd()
    try:
        os.chdir(run_directory)
        for simulation in args.simulations:
            simtools.process_run(simulation)
    finally:
        os.chdir(previous_directory)

    print("Wrote result files and PDF plots to " + str(run_directory))


if __name__ == "__main__":
    main()
