"""Create quick-look PNG plots from processed AtRIS response files."""

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from .input_plotting import plot_inputs, read_macro
from .phantoms import read_phantoms
from .postprocess import get_histogram_axes, warn_if_inputs_do_not_match_output


def _log_norm(data):
    positive = data[np.isfinite(data) & (data > 0)]
    if not positive.size:
        return None
    return LogNorm(vmin=np.min(positive), vmax=np.max(positive))


def _centers_to_edges(centers):
    if centers.size == 1:
        return np.array([centers[0] - 0.5, centers[0] + 0.5])
    edges = np.empty(centers.size + 1)
    edges[1:-1] = (centers[:-1] + centers[1:]) / 2.0
    edges[0] = centers[0] - (centers[1] - centers[0]) / 2.0
    edges[-1] = centers[-1] + (centers[-1] - centers[-2]) / 2.0
    return edges


def _read_raw_histogram(filename, skiprows):
    return np.atleast_2d(np.loadtxt(filename, delimiter=",", skiprows=skiprows))


def _read_response(filename):
    data = np.atleast_2d(np.loadtxt(filename))
    return data[:, 1], data[:, 2:]


def _add_response_plot(
    figure,
    axis,
    histogram,
    energy_edges,
    altitude_edges,
    maximum_altitude,
    title,
):
    mesh = axis.pcolormesh(
        energy_edges,
        altitude_edges,
        histogram,
        norm=_log_norm(histogram),
        shading="flat",
        rasterized=True,
    )
    axis.set_title(title)
    axis.set_xlabel("Primary kinetic energy [MeV]")
    axis.set_ylabel("Altitude [km]")
    axis.set_xscale("log")
    axis.set_ylim(0, maximum_altitude)
    figure.colorbar(mesh, ax=axis, label="Response per primary")


def _angular_values(histogram, axes):
    xbins = len(axes[0]) - 1
    ybins = len(axes[1]) - 1
    values = histogram[:, 0].reshape((ybins + 2, xbins + 2))
    return values[1:-1, 1:-1]


def _add_angular_plot(figure, axis, histogram, axes, title):
    values = _angular_values(histogram, axes)
    mesh = axis.pcolormesh(
        axes[0],
        axes[1],
        values,
        norm=_log_norm(values),
        shading="flat",
        rasterized=True,
    )
    axis.set_title(title)
    axis.set_xlabel("Azimuth phi [rad]")
    axis.set_ylabel("cos(theta)")
    figure.colorbar(mesh, ax=axis, label="Primaries")


def _save_generic_plot(
    primary_energy,
    configured_energy,
    direction,
    position,
    ionization,
    energy_edges,
    direction_axes,
    position_axes,
    altitude_edges,
    maximum_altitude,
    species,
    filename,
):
    figure, axes = plt.subplots(ncols=2, nrows=2, figsize=(12, 10))

    primary_counts = primary_energy[1:-1, 0]
    axes[0, 0].stairs(
        primary_counts,
        energy_edges,
        label="Simulated",
    )
    if configured_energy.size:
        configured_weights = configured_energy[1:, 1]
        weight_sum = np.sum(configured_weights)
        if weight_sum > 0:
            expected_counts = configured_weights * np.sum(primary_counts) / weight_sum
            axes[0, 0].stairs(
                expected_counts,
                configured_energy[:, 0],
                linestyle="--",
                label="Configured",
            )
    axes[0, 0].set_title(species + " primary energy")
    axes[0, 0].set_xlabel("Primary kinetic energy [MeV]")
    axes[0, 0].set_ylabel("Primaries")
    axes[0, 0].set_xscale("log")
    axes[0, 0].legend()

    _add_angular_plot(
        figure,
        axes[0, 1],
        direction,
        direction_axes,
        species + " source direction",
    )
    _add_angular_plot(
        figure,
        axes[1, 0],
        position,
        position_axes,
        species + " source position",
    )
    _add_response_plot(
        figure,
        axes[1, 1],
        ionization,
        energy_edges,
        altitude_edges,
        maximum_altitude,
        species + " ionization",
    )

    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)


def _save_phantom_plot(
    histograms,
    titles,
    energy_edges,
    altitude_edges,
    maximum_altitude,
    filename,
):
    figure, axes = plt.subplots(
        ncols=len(histograms),
        figsize=(6 * len(histograms), 5),
        sharey=True,
        squeeze=False,
    )
    for index, (histogram, title) in enumerate(zip(histograms, titles)):
        _add_response_plot(
            figure,
            axes[0, index],
            histogram,
            energy_edges,
            altitude_edges,
            maximum_altitude,
            title,
        )
        if index:
            axes[0, index].set_ylabel("")
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)


def _get_processed_phantom_ids(simname):
    pattern = re.compile(
        "^" + re.escape(simname) + r"\.(?:dose|equi|rates)(\d+)$"
    )
    return sorted(
        {
            int(match.group(1))
            for filename in os.listdir(".")
            if (match := pattern.match(filename)) is not None
        }
    )


def _has_processed_output(simname):
    pattern = re.compile(
        "^" + re.escape(simname) + r"\.(?:ioni|dose\d+|equi\d+|rates\d+)$"
    )
    return any(
        pattern.match(filename) is not None
        for filename in os.listdir(".")
    )


def plot_run(simname):
    filenames = []
    errors = []
    species = simname.capitalize()
    if Path(simname + "_h1_h1.1.csv").is_file():
        warn_if_inputs_do_not_match_output(simname)
    try:
        if Path(simname + "_h1_h1.1.csv").is_file():
            energy_edges = get_histogram_axes(simname + "_h1_h1.1.csv")[0]
        else:
            energy_edges = np.atleast_1d(np.loadtxt(simname + ".bins"))
    except Exception as error:
        return filenames, ["%s results: %s" % (simname, error)]

    configured_energy = np.empty((0, 2))
    if Path(simname + ".mac").is_file():
        try:
            _, configured_energy = read_macro(simname + ".mac")
        except Exception as error:
            errors.append("%s energy input: %s" % (simname, error))

    if Path(simname + ".ioni").is_file():
        try:
            direction_axes = get_histogram_axes(simname + "_h2_h2.dir.csv")
            position_axes = get_histogram_axes(simname + "_h2_h2.pos.csv")
            primary_energy = _read_raw_histogram(simname + "_h1_h1.1.csv", 7)
            direction = _read_raw_histogram(simname + "_h2_h2.dir.csv", 10)
            position = _read_raw_histogram(simname + "_h2_h2.pos.csv", 10)
            altitudes, ionization = _read_response(simname + ".ioni")
            filename = simname + ".png"
            _save_generic_plot(
                primary_energy,
                configured_energy,
                direction,
                position,
                ionization,
                energy_edges,
                direction_axes,
                position_axes,
                _centers_to_edges(altitudes),
                altitudes[-1],
                species,
                filename,
            )
            filenames.append(filename)
        except Exception as error:
            errors.append("%s general results: %s" % (simname, error))

    try:
        phantom_names = {
            phantom["id"]: phantom["stem"]
            for phantom in read_phantoms(Path.cwd())
        }
    except Exception as error:
        phantom_names = {}
        errors.append("phantom metadata: " + str(error))

    quantities = ("dose", "equi", "rates")
    titles = ("absorbed dose", "dose equivalent", "count rate")
    for phantom_id in _get_processed_phantom_ids(simname):
        responses = []
        response_titles = []
        altitudes = None
        for quantity, title in zip(quantities, titles):
            response_file = "%s.%s%i" % (simname, quantity, phantom_id)
            if not Path(response_file).is_file():
                errors.append("%s results: missing %s" % (simname, response_file))
                continue
            try:
                response_altitudes, response = _read_response(response_file)
            except Exception as error:
                errors.append("%s: %s" % (response_file, error))
                continue
            if altitudes is None:
                altitudes = response_altitudes
            elif not np.array_equal(response_altitudes, altitudes):
                errors.append("%s: altitude values do not match" % response_file)
                continue
            responses.append(response)
            response_titles.append(title)

        if not responses:
            continue
        phantom_name = phantom_names.get(phantom_id, "phantom-%i" % phantom_id)
        filename = "%s.%s.png" % (simname, phantom_name)
        try:
            _save_phantom_plot(
                responses,
                [
                    "%s %s, %s" % (species, title, phantom_name)
                    for title in response_titles
                ],
                energy_edges,
                _centers_to_edges(altitudes),
                altitudes[-1],
                filename,
            )
            filenames.append(filename)
        except Exception as error:
            errors.append("%s results: %s" % (simname, error))
    return filenames, errors


def main():
    parser = argparse.ArgumentParser(
        description="Plot AtRIS inputs and processed response files."
    )
    parser.add_argument("run_directory", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()

    run_directory = args.run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise SystemExit("Run directory does not exist: " + str(run_directory))

    previous_directory = Path.cwd()
    input_plots = []
    plotted = []
    errors = []
    try:
        os.chdir(run_directory)
        try:
            input_plots, input_errors = plot_inputs()
            errors.extend(input_errors)
        except Exception as error:
            errors.append("inputs: " + str(error))
        for simulation in ("protons", "alphas"):
            if not _has_processed_output(simulation):
                print("Skipping " + simulation + ": processed output not found.")
                continue
            try:
                result_plots, result_errors = plot_run(simulation)
                plotted.extend(result_plots)
                errors.extend(result_errors)
            except Exception as error:
                errors.append("%s results: %s" % (simulation, error))
    finally:
        os.chdir(previous_directory)

    for error in errors:
        print("Could not plot " + error, file=sys.stderr)
    if input_plots:
        print("Wrote input PNG plots to " + str(run_directory))
    if plotted:
        print("Wrote PNG plots to " + str(run_directory))
    elif not input_plots:
        print("No processed simulation output found in " + str(run_directory))


if __name__ == "__main__":
    main()
