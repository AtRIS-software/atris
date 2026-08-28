#!/usr/bin/env python3
"""Post-process AtRIS CSV output and create response plots."""

import argparse
import os
import re
import sys
import warnings
from pathlib import Path

import numpy as np

from .phantoms import read_phantoms


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


def get_histogram_axes(filename):
    axes = []
    with open(filename, "r") as histogram:
        for line in histogram:
            if line.startswith("#axis edges "):
                axes.append(
                    np.fromstring(line[len("#axis edges ") :], sep=" ")
                )
            elif line.startswith("#axis fixed "):
                fields = line.split()
                axes.append(
                    np.linspace(
                        float(fields[3]),
                        float(fields[4]),
                        int(fields[2]) + 1,
                    )
                )
            elif line.startswith("entries,"):
                break
    if not axes:
        raise ValueError("No histogram axes found in " + str(filename))
    return axes


def get_energy_edges(simname):
    edges = get_histogram_axes(simname + "_h1_h1.1.csv")[0]
    print("This simulation had %i energy bins" % (edges.shape[0] - 1))
    return edges


def _read_macro_configuration(filename):
    energy_edges = []
    event_count = None
    with open(filename) as macro:
        for line in macro:
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            if fields[0] == "/gps/hist/point":
                energy_edges.append(float(fields[1]))
            elif fields[0] == "/run/beamOn":
                event_count = int(fields[1])
    return np.asarray(energy_edges), event_count


def input_output_warnings(simname):
    warnings = []
    histogram_path = Path(simname + "_h1_h1.1.csv")
    bins_path = Path(simname + ".bins")
    macro_path = Path(simname + ".mac")

    output_edges = get_histogram_axes(histogram_path)[0]
    input_edges = None
    if bins_path.is_file():
        input_edges = np.atleast_1d(np.loadtxt(bins_path))
        if (
            input_edges.shape != output_edges.shape
            or not np.allclose(input_edges, output_edges)
        ):
            warnings.append(
                "%s: %s does not match the energy edges recorded in %s"
                % (simname, bins_path.name, histogram_path.name)
            )

    if macro_path.is_file():
        macro_edges, event_count = _read_macro_configuration(macro_path)
        if input_edges is not None and (
            macro_edges.shape != input_edges.shape
            or not np.allclose(macro_edges, input_edges)
        ):
            warnings.append(
                "%s: %s energy edges do not match %s"
                % (simname, macro_path.name, bins_path.name)
            )
        if event_count is not None and not Path("chunks.txt").is_file():
            primary_energy = np.atleast_2d(
                np.loadtxt(histogram_path, delimiter=",", skiprows=7)
            )
            recorded_events = int(np.sum(primary_energy[1:-1, 0]))
            if recorded_events != event_count:
                warnings.append(
                    "%s: %s requests %i events, but %s records %i"
                    % (
                        simname,
                        macro_path.name,
                        event_count,
                        histogram_path.name,
                        recorded_events,
                    )
                )

    psf_path = Path("simulation.psf")
    ionization_path = Path(simname + "_h2_h2.ion.csv")
    if psf_path.is_file() and ionization_path.is_file():
        detector_count = np.atleast_2d(np.loadtxt(psf_path)).shape[0]
        output_detector_count = len(get_histogram_axes(ionization_path)[1]) - 1
        if output_detector_count != detector_count:
            warnings.append(
                "%s: %s defines %i detector layers, but %s records %i"
                % (
                    simname,
                    psf_path.name,
                    detector_count,
                    ionization_path.name,
                    output_detector_count,
                )
            )

    phantom_path = Path("phantoms.txt")
    if phantom_path.is_file():
        configured_phantoms = len(read_phantoms(Path.cwd()))
        output_phantoms = sum(
            re.match(
                "^" + re.escape(simname) + r"_h2_h2\.dos\d+\.csv$",
                filename,
            )
            is not None
            for filename in os.listdir(".")
        )
        if output_phantoms != configured_phantoms:
            warnings.append(
                "%s: %s defines %i phantoms, but raw output contains %i"
                % (
                    simname,
                    phantom_path.name,
                    configured_phantoms,
                    output_phantoms,
                )
            )
    return warnings


def warn_if_inputs_do_not_match_output(simname):
    for warning in input_output_warnings(simname):
        print("WARNING: " + warning, file=sys.stderr)


def process_phantoms(nrphantoms):
    if nrphantoms == 0:
        return np.empty((0, 2))
    phantoms = read_phantoms(Path.cwd())
    if len(phantoms) < nrphantoms:
        raise ValueError(
            "AtRIS produced output for more phantoms than phantoms.txt defines"
        )
    return np.array(
        [
            [phantom["mass"], phantom["area"]]
            for phantom in phantoms[:nrphantoms]
        ]
    )


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

    warn_if_inputs_do_not_match_output(simname)
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
