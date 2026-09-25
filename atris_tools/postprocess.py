#!/usr/bin/env python3
"""Convert raw AtRIS histograms into scaled numerical response files."""

import argparse
import logging
import os
from pathlib import Path

import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .phantoms import read_phantoms
from .psf import load_psf
from .response_histograms import (
    IONIZATION_HISTOGRAM,
    PRIMARY_HISTOGRAM,
    ResponseHistogramReader,
    csv_histogram_path,
    csv_histogram_axes,
    response_output_format,
)


logger = logging.getLogger(__name__)


def process_psf(filename="simulation.psf"):
    data = load_psf(filename)
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
    with ResponseHistogramReader(simname) as histograms:
        nrphantoms = histograms.phantom_count()
    logger.debug("%s output includes %i phantoms", simname, nrphantoms)
    return nrphantoms


def get_histogram_axes(filename):
    return csv_histogram_axes(filename)


def get_energy_edges(simname, histograms=None):
    if histograms is None:
        with ResponseHistogramReader(simname) as source:
            return get_energy_edges(simname, source)
    edges = histograms.axes(PRIMARY_HISTOGRAM)[0]
    logger.debug("%s output includes %i energy bins", simname, edges.shape[0] - 1)
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


def _input_output_warnings(simname, histograms):
    warnings = []
    def output_name(name):
        if histograms.format == "root":
            return simname + ".root"
        return csv_histogram_path(simname, name).name

    bins_path = Path(simname + ".bins")
    macro_path = Path(simname + ".mac")

    output_edges = histograms.axes(PRIMARY_HISTOGRAM)[0]
    input_edges = None
    if bins_path.is_file():
        input_edges = np.atleast_1d(np.loadtxt(bins_path))
        if (
            input_edges.shape != output_edges.shape
            or not np.allclose(input_edges, output_edges)
        ):
            warnings.append(
                "%s: %s does not match the energy edges recorded in %s"
                % (simname, bins_path.name, output_name(PRIMARY_HISTOGRAM))
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
            primary_energy = histograms.data(PRIMARY_HISTOGRAM)
            recorded_events = int(np.sum(primary_energy[1:-1, 0]))
            if recorded_events != event_count:
                warnings.append(
                    "%s: %s requests %i events, but %s records %i"
                    % (
                        simname,
                        macro_path.name,
                        event_count,
                        output_name(PRIMARY_HISTOGRAM),
                        recorded_events,
                    )
                )

    psf_path = Path("simulation.psf")
    if psf_path.is_file() and IONIZATION_HISTOGRAM in histograms.names():
        detector_count = load_psf(psf_path).shape[0]
        output_detector_count = len(histograms.axes(IONIZATION_HISTOGRAM)[1]) - 1
        if output_detector_count != detector_count:
            warnings.append(
                "%s: %s defines %i detector layers, but %s records %i"
                % (
                    simname,
                    psf_path.name,
                    detector_count,
                    output_name(IONIZATION_HISTOGRAM),
                    output_detector_count,
                )
            )

    phantom_path = Path("phantoms.txt")
    if phantom_path.is_file():
        configured_phantoms = len(read_phantoms(Path.cwd()))
        output_phantoms = histograms.phantom_count()
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


def input_output_warnings(simname):
    with ResponseHistogramReader(simname) as histograms:
        return _input_output_warnings(simname, histograms)


def warn_if_inputs_do_not_match_output(simname):
    for warning in input_output_warnings(simname):
        logger.warning("%s", warning)


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


def read_data(simname, nphant, histograms=None):
    if histograms is None:
        with ResponseHistogramReader(simname) as source:
            return read_data(simname, nphant, source)
    names = [PRIMARY_HISTOGRAM, "h2.dir", "h2.pos", IONIZATION_HISTOGRAM]
    for phantom_nr in range(nphant):
        names.append("h2.dos" + str(phantom_nr))
        names.append("h2.equi" + str(phantom_nr))
        names.append("h2.rates" + str(phantom_nr))

    return [histograms.data(name) for name in names]


def scale_data(data, nphant, ndet, nenergyedges, phantom_data, geometry):
    nrparticles = data[0][:, 0]
    nrparticles = nrparticles[1:-1]
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
    with ResponseHistogramReader(simname) as histograms:
        for warning in _input_output_warnings(simname, histograms):
            logger.warning("%s", warning)
        geometry, detector_count = process_psf()
        phantom_count = histograms.phantom_count()
        energy_edges = get_energy_edges(simname, histograms)
        phantom_data = process_phantoms(phantom_count)
        logger.info(
            "Post-processing %s %s output with %i energy bins and %i phantoms",
            simname,
            histograms.format.upper(),
            energy_edges.shape[0] - 1,
            phantom_count,
        )
        logger.debug("Reading %s histogram data", simname)
        data = read_data(simname, phantom_count, histograms)
    logger.debug("Scaling %s response data", simname)
    scaled_data = scale_data(
        data,
        phantom_count,
        detector_count,
        energy_edges.shape[0],
        phantom_data,
        geometry,
    )
    logger.debug("Writing %s response files", simname)
    make_output(scaled_data, geometry, simname, phantom_count)
    logger.info("Wrote processed %s response files", simname)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Scale canonical AtRIS CSV or ROOT histograms into altitude- and "
            "energy-dependent ionization and phantom response tables."
        ),
        epilog=(
            "The command processes the protons and alphas prefixes when their "
            "primary histogram files are present. It reads simulation.psf and, "
            "for phantom responses, phantoms.txt; it writes .ioni, .doseN, "
            ".equiN, and .ratesN files, replacing existing processed files. "
            "Missing species are skipped. This command does not gather chunk "
            "histograms, run simulations, or make plots."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        metavar="RUN_DIRECTORY",
        help="Run directory containing canonical response output (default: current directory).",
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    run_directory = args.run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise SystemExit("Run directory does not exist: " + str(run_directory))

    previous_directory = Path.cwd()
    processed = []
    logger.info("Starting post-processing in %s", run_directory)
    try:
        os.chdir(run_directory)
        for simulation in ("protons", "alphas"):
            if response_output_format(simulation) is None:
                logger.info("Skipping %s: output not found", simulation)
                continue
            process_run(simulation)
            processed.append(simulation)
    finally:
        os.chdir(previous_directory)

    if processed:
        logger.info("Wrote processed result files to %s", run_directory)
    else:
        logger.info("No requested simulation output found in %s", run_directory)


if __name__ == "__main__":
    main()
