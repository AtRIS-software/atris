#!/usr/bin/env python3
"""Post-process AtRIS CSV output and create response plots."""

import argparse
import os
import re
import warnings
from pathlib import Path

import numpy as np


os.environ.setdefault("MPLBACKEND", "Agg")


warnings.filterwarnings("ignore")


def process_psf(filename="simulation.psf"):
    data = np.atleast_2d(np.loadtxt(filename))
    rmin = data[:, 0] * 100000.0
    rmax = data[:, 1] * 100000.0
    delta_phi = data[:, 3] - data[:, 2]
    theta_factor = np.cos(data[:, 4]) - np.cos(data[:, 5])
    inner_surface = delta_phi * rmin**2 * theta_factor
    outer_surface = delta_phi * rmax**2 * theta_factor
    volume = delta_phi * theta_factor * (rmax**3 - rmin**3) / 3.0

    core = inner_surface == 0
    inner_surface[core] = outer_surface[core]

    order = np.argsort(inner_surface, kind="stable")
    geometry = {
        "sdid": data[:, 6].astype(int)[order],
        "volume/cm3": volume[order],
        "inn_surface/cm2": inner_surface[order],
    }
    return geometry, data.shape[0]


def get_nr_phantoms(simname):
    pattern = re.compile("^" + re.escape(simname) + r"_h2_h2\.dos\d+\.csv$")
    nrphantoms = sum(
        pattern.match(filename) is not None for filename in os.listdir(".")
    )
    label = "phantom" if nrphantoms == 1 else "phantoms"
    print("This run included %i %s" % (nrphantoms, label))
    return nrphantoms


def get_energy_edges(simname):
    with open(simname + "_h1_h1.1.csv", "r") as histogram:
        axis_line = next(
            line for line in histogram if line.startswith("#axis edges ")
        )
    edges = np.fromstring(axis_line[len("#axis edges ") :], sep=" ")
    print("This simulation had %i energy bins" % (edges.shape[0] - 1))
    return edges


def process_phantoms(nrphantoms):
    phantoms = np.loadtxt(
        "phantoms.txt",
        delimiter=",",
        comments="#",
        usecols=(0, 1),
        ndmin=2,
    )
    return phantoms[:nrphantoms]


def read_data(simname, nphant):
    names = ["_h1_h1.1", "_h2_h2.dir", "_h2_h2.pos", "_h2_h2.ion"]
    for phantom_nr in range(nphant):
        names.append("_h2_h2.dos" + str(phantom_nr))
        names.append("_h2_h2.equi" + str(phantom_nr))
        names.append("_h2_h2.rates" + str(phantom_nr))

    simulation_data = []
    for index, name in enumerate(names):
        filename = simname + name + ".csv"
        skiprows = 7 if index == 0 else 10
        simulation_data.append(np.loadtxt(filename, delimiter=",", skiprows=skiprows))
    return simulation_data


def scale_data(data, nphant, ndet, nenergyedges, phantom_data, geometry):
    nrparticles = data[0][:, 0]
    nrparticles = nrparticles[1:-1]
    print(nrparticles)
    limit = 1 + nphant * 3
    shapex = ndet + 2
    shapey = nenergyedges + 1
    for hist_index in range(3, 3 + limit):
        new_data = data[hist_index][:, 1].reshape((shapex, shapey))
        new_data = new_data[1:-1, 1:-1]
        data[hist_index] = new_data / nrparticles[None, :]
        if hist_index == 3:
            data[hist_index] = data[hist_index] / geometry["volume/cm3"][:, None]
        if hist_index > 3:
            phantom_nr = int((hist_index - 4) / 3)
            phantom_surface = phantom_data[phantom_nr, 1]
            if ((hist_index - 4) % 3) != 2:
                phantom_surface = phantom_surface / phantom_data[phantom_nr, 0]
            data[hist_index] = (
                data[hist_index]
                * phantom_surface
                / geometry["inn_surface/cm2"][:, None]
            )
    return data


def make_output(data, geometry, simname, nphant):
    altitude = (geometry["inn_surface/cm2"] / (4.0 * np.pi)) ** 0.5 / 100000.0
    altitude = altitude - altitude[2]
    altitude = altitude[1:-1, None]
    sdid = geometry["sdid"][1:-1, None]
    extensions = [".dose", ".equi", ".rates"]
    number_format = ["%.5e"] * data[3].shape[1]
    number_format = ["%8.3f"] + number_format
    number_format = ["%5i"] + number_format
    for hist_index in range(3, 3 + 1 + nphant * 3):
        if hist_index == 3:
            extension = ".ioni"
        else:
            extension = extensions[(hist_index - 4) % 3] + str(
                int((hist_index - 4) / 3)
            )
        histogram_data = data[hist_index][1:-1, :]
        output_data = np.hstack((sdid, altitude, histogram_data))
        np.savetxt(
            simname + extension,
            output_data,
            fmt=number_format,
            delimiter=" ",
            encoding="utf-8",
        )


def process_run(simname):
    try:
        from .plotting import make_allplots
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PDF plotting requires the atris-tools 'plot' extra."
        ) from exc

    geometry, detector_count = process_psf()
    phantom_count = get_nr_phantoms(simname)
    energy_edges = get_energy_edges(simname)
    phantom_data = process_phantoms(phantom_count)
    print("Processing phantoms")
    data = read_data(simname, phantom_count)
    print("Reading data complete.")
    scaled_data = scale_data(
        data,
        phantom_count,
        detector_count,
        energy_edges.shape[0],
        phantom_data,
        geometry,
    )
    make_allplots(
        scaled_data,
        energy_edges,
        geometry,
        simname,
        phantom_count,
    )
    print("Making output files.")
    make_output(scaled_data, geometry, simname, phantom_count)
    print("Response files have been created.")


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
            process_run(simulation)
    finally:
        os.chdir(previous_directory)

    print("Wrote result files and PDF plots to " + str(run_directory))


if __name__ == "__main__":
    main()
