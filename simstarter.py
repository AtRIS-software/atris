#!/usr/bin/env python3
"""Prepare, run, and post-process an AtRIS simulation."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

repository_dir = Path(__file__).resolve().parent
workspace_dir = repository_dir.parent

import atrismacrogen as amg
import atristoolset as ia
import simtools as st


longitude = 10.00
latitude = 10.00
year = 2012
month = 5
day = 27
hour_utc = 12.0
alt_max = 100.0
alt_step = 0.2
numberparts = 2
alpha_factor = 0.66
phys_list = "FTFP_BERT_HP"
alt_min = 0.0
phantom_count = 1


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare, run, and post-process a small AtRIS simulation."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="New run directory (default: the next numbered directory under <ATRIS_WORK>/runs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare the run directory without starting AtRIS.",
    )
    return parser.parse_args()


def create_run_directory(configured_path):
    if configured_path is None:
        runs_dir = workspace_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        number = 1
        while True:
            run_dir = runs_dir / ("run-" + str(number).zfill(3))
            try:
                run_dir.mkdir(exist_ok=False)
                return run_dir
            except FileExistsError:
                number += 1

    run_dir = configured_path.expanduser().resolve()
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit("Run directory already exists: " + str(run_dir))
    return run_dir


def copy_simulation_files(run_dir):
    phantom_dir = repository_dir / "phantoms"
    filenames = ["phantoms.txt"]
    for number in range(phantom_count):
        filenames.append("radiation_phantom" + str(number) + ".txt")
        filenames.append("counting_phantom" + str(number) + ".txt")
    for filename in filenames:
        shutil.copy2(phantom_dir / filename, run_dir / filename)
    print("Copied " + str(phantom_count) + " phantom pair to " + str(run_dir))


def prepare_simulation(run_dir):
    os.chdir(run_dir)
    atmosphere = st.get_atmosphere(
        year,
        month,
        day,
        hour_utc,
        longitude,
        latitude,
        alt_min,
        alt_max,
        alt_step,
    )
    atmosphere = st.nrlm_reformer(atmosphere)
    st.nrml2psf(atmosphere)
    st.psf2gdml()
    phi = st.find_phi(year, month, day, hour_utc)
    copy_simulation_files(run_dir)
    return phi


def run_simulation(run_dir, atris_executable, simname):
    command = [
        str(atris_executable),
        phys_list,
        simname,
        "-1",
        str(phantom_count),
    ]
    log_path = run_dir / (simname + ".log")
    print("Running " + simname + "; full output: " + str(log_path))
    with open(log_path, "w") as log_file:
        process = subprocess.Popen(
            command,
            cwd=run_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            if (
                "### AtRIS: Starting the simulation" in line
                or "### AtRIS: the simulation has completed" in line
                or "AtRIS progress:" in line
                or "G4Exception" in line
                or "ERROR" in line
                or "CAUGHT SIGNAL" in line
            ):
                print(line, end="")
        return_code = process.wait()

    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def main():
    args = parse_args()
    run_dir = create_run_directory(args.run_dir)
    atris_executable = repository_dir / "atris" / "build" / "AtRIS"
    numberthreads = ia.get_threads()

    print("Run directory: " + str(run_dir))
    print("Worker threads: " + str(numberthreads))

    phi = prepare_simulation(run_dir)
    amg.macroGenManager(
        numberparts,
        numberthreads,
        alpha_factor,
        str(run_dir),
        energy_max_power=3,
        energy_points=7,
    )
    print(phi)

    if args.dry_run:
        print("Run directory prepared; AtRIS was not started.")
        return

    run_simulation(run_dir, atris_executable, "protons")
    run_simulation(run_dir, atris_executable, "alphas")

    os.chdir(run_dir)
    st.process_run("protons")
    st.process_run("alphas")


if __name__ == "__main__":
    main()
