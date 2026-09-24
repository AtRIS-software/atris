"""Create quick-look PNG plots from processed AtRIS response files."""

import argparse
import logging
import os
import re
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .input_plotting import (
    log_norm,
    plot_inputs,
    read_layers,
    read_macro,
    setup_shell_axis,
    shell_coordinates,
)
from .interface_plotting import plot_interface_output
from .phantoms import read_phantoms
from .postprocess import get_histogram_axes, warn_if_inputs_do_not_match_output
from .step_plotting import plot_mode_one_output


logger = logging.getLogger(__name__)


def _read_raw_histogram(filename, skiprows):
    return np.atleast_2d(np.loadtxt(filename, delimiter=",", skiprows=skiprows))


def _read_response(filename):
    data = np.atleast_2d(np.loadtxt(filename))
    return data[:, 0], data[:, 2:]


def _convergence_ymax(series):
    """Set plot scale from the lowest 90% of finite convergence values."""
    values = np.concatenate([np.ravel(values) for values in series])
    values = values[np.isfinite(values)]
    return 1.05 * np.percentile(values, 90)


def _log_125_ticks(limits):
    """Return labelled 1-2-5 ticks and the remaining log subdivisions."""
    lower, upper = limits
    powers = 10.0 ** np.arange(
        np.floor(np.log10(lower)),
        np.ceil(np.log10(upper)) + 1,
    )
    major = np.ravel(np.outer(powers, (1, 2, 5)))
    minor = np.ravel(np.outer(powers, (3, 4, 6, 7, 8, 9)))
    return (
        major[(major >= lower) & (major <= upper)],
        minor[(minor >= lower) & (minor <= upper)],
    )


def _inverse_sqrt_reference(completed_chunks, values, reference_chunks=None):
    """Return a robustly scaled inverse-square-root reference curve."""
    completed_chunks = np.asarray(completed_chunks)
    values = np.asarray(values)
    finite = np.isfinite(values) & (values >= 0)
    amplitude = np.median(
        values[finite] * np.sqrt(completed_chunks[finite])
    )
    if reference_chunks is None:
        reference_chunks = completed_chunks
    return amplitude / np.sqrt(reference_chunks)


def _plot_striped_guide(axis, chunks, values, color, label):
    """Plot an alternating black and coloured guide above the data."""
    axis.plot(
        chunks,
        values,
        color="black",
        linewidth=1.6,
        zorder=5,
        label="_nolegend_",
    )
    axis.plot(
        chunks,
        values,
        color=color,
        linestyle=(0, (5, 5)),
        linewidth=1.6,
        dash_capstyle="butt",
        zorder=6,
        label="_nolegend_",
    )
    if label != "_nolegend_":
        axis.plot(
            [],
            [],
            color="black",
            linestyle="--",
            linewidth=1.6,
            label=label,
        )


def _add_inverse_sqrt_guides(
    axis, completed_chunks, planned_chunks, lines, series
):
    """Add colour-matched inverse-square-root guides to convergence curves."""
    reference_chunks = np.geomspace(
        completed_chunks[0], planned_chunks, 300
    )
    for index, (line, values) in enumerate(zip(lines, series)):
        _plot_striped_guide(
            axis,
            reference_chunks,
            _inverse_sqrt_reference(
                completed_chunks, values, reference_chunks
            ),
            line.get_color(),
            r"$1/\sqrt{N}$ guides" if index == 0 else "_nolegend_",
        )


def _recent_power_law_fit(completed_chunks, values, reference_chunks=None):
    """Fit a power law to the most recent half of the observations."""
    completed_chunks = np.asarray(completed_chunks, dtype=float)
    values = np.asarray(values, dtype=float)
    finite = (
        np.isfinite(completed_chunks)
        & np.isfinite(values)
        & (completed_chunks > 0)
        & (values > 0)
    )
    chunks = completed_chunks[finite]
    observed = values[finite]
    if chunks.size < 2:
        return None

    recent = chunks >= chunks[-1] / 2.0
    exponent, log_amplitude = np.polyfit(
        np.log(chunks[recent]), np.log(observed[recent]), 1
    )
    if reference_chunks is None:
        reference_chunks = completed_chunks
    reference_chunks = np.asarray(reference_chunks, dtype=float)
    return np.exp(log_amplitude) * reference_chunks ** exponent


def _add_uncertainty_fits(
    axis, completed_chunks, planned_chunks, lines, series
):
    """Add recent empirical power-law fits to the uncertainty curves."""
    reference_chunks = np.geomspace(
        completed_chunks[0], planned_chunks, 300
    )
    labelled = False
    for line, values in zip(lines, series):
        fitted = _recent_power_law_fit(
            completed_chunks, values, reference_chunks
        )
        if fitted is None:
            continue
        _plot_striped_guide(
            axis,
            reference_chunks,
            fitted,
            line.get_color(),
            (
                "Recent power-law fits"
                if not labelled
                else "_nolegend_"
            ),
        )
        labelled = True


def _planned_chunks(simname):
    """Return the number of planned chunks for one particle species."""
    count = 0
    with open("chunks.txt") as plan:
        for line in plan:
            fields = line.split()
            if fields and fields[0] == simname:
                count += 1
    return count


def _add_response_plot(
    axis,
    histogram,
    energy_edges,
    detector_ids,
    layers,
    title,
):
    _, positions, plot_edges = shell_coordinates(layers, detector_ids)
    mesh = axis.pcolormesh(
        energy_edges,
        plot_edges,
        histogram,
        norm=log_norm(histogram),
        shading="flat",
        rasterized=True,
    )
    setup_shell_axis(axis, positions)
    axis.set_title(title)
    axis.set_xlabel("Primary kinetic energy [MeV]")
    axis.set_xscale("log")
    axis.figure.colorbar(mesh, ax=axis, label="Response per primary")


def _angular_values(histogram, axes):
    xbins = len(axes[0]) - 1
    ybins = len(axes[1]) - 1
    values = histogram[:, 0].reshape((ybins + 2, xbins + 2))
    return values[1:-1, 1:-1]


def _add_angular_plot(axis, histogram, axes, title):
    values = _angular_values(histogram, axes)
    mesh = axis.pcolormesh(
        axes[0],
        axes[1],
        values,
        norm=log_norm(values),
        shading="flat",
        rasterized=True,
    )
    axis.set_title(title)
    axis.set_xlabel("Azimuth phi [rad]")
    axis.set_ylabel("cos(theta)")
    axis.figure.colorbar(mesh, ax=axis, label="Primaries")


def _save_generic_plot(
    primary_energy,
    configured_energy,
    direction,
    position,
    ionization,
    energy_edges,
    direction_axes,
    position_axes,
    detector_ids,
    layers,
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
        axes[0, 1],
        direction,
        direction_axes,
        species + " source direction",
    )
    _add_angular_plot(
        axes[1, 0],
        position,
        position_axes,
        species + " source position",
    )
    _add_response_plot(
        axes[1, 1],
        ionization,
        energy_edges,
        detector_ids,
        layers,
        species + " ionization",
    )

    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)


def _save_phantom_plot(
    histograms,
    titles,
    energy_edges,
    detector_ids,
    layers,
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
            axes[0, index],
            histogram,
            energy_edges,
            detector_ids,
            layers,
            title,
        )
        if index:
            axes[0, index].set_ylabel("")
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)


def plot_convergence(simname):
    """Plot the ionization convergence table produced by atris-gather."""
    data = np.atleast_1d(
        np.genfromtxt(
            simname + ".convergence.csv",
            delimiter=",",
            names=True,
        )
    )
    species = {"protons": "Proton", "alphas": "Alpha"}[simname]
    planned_chunks = _planned_chunks(simname)
    figure, axes = plt.subplots(nrows=2, figsize=(8, 8), sharex=True)
    change_series = (
        data["ionization_change_percent"],
        data["cell_change_p50_percent"],
        data["cell_change_p90_percent"],
    )
    change_lines = [
        axes[0].plot(
            data["completed_chunks"],
            change_series[0],
            marker="o",
            label="Whole panel",
        )[0],
        axes[0].plot(
            data["completed_chunks"],
            change_series[1],
            marker="o",
            label="Median cell",
        )[0],
        axes[0].plot(
            data["completed_chunks"],
            change_series[2],
            marker="o",
            label="90th percentile cell",
        )[0],
    ]
    _add_inverse_sqrt_guides(
        axes[0],
        data["completed_chunks"],
        planned_chunks,
        change_lines,
        change_series,
    )
    axes[0].set_title("Change after latest chunk group")
    axes[0].set_ylabel("Ionization change [%]")
    axes[0].legend()

    uncertainty_series = (
        data["cell_relative_se_p50_percent"],
        data["cell_relative_se_p90_percent"],
    )
    uncertainty_lines = [
        axes[1].plot(
            data["completed_chunks"],
            uncertainty_series[0],
            marker="o",
            label="Median cell",
        )[0],
        axes[1].plot(
            data["completed_chunks"],
            uncertainty_series[1],
            marker="o",
            label="90th percentile cell",
        )[0],
    ]
    _add_uncertainty_fits(
        axes[1],
        data["completed_chunks"],
        planned_chunks,
        uncertainty_lines,
        uncertainty_series,
    )
    axes[1].set_title("Estimated Monte Carlo uncertainty")
    axes[1].set_xlabel("Completed chunks")
    axes[1].set_ylabel("Relative standard error [%]")
    axes[1].legend()

    for axis in axes:
        axis.set_yscale("log")
        axis.grid(alpha=0.25)
    axes[0].set_ylim(top=_convergence_ymax(change_series))
    axes[1].set_ylim(top=_convergence_ymax(uncertainty_series))
    for axis in axes:
        major_ticks, minor_ticks = _log_125_ticks(axis.get_ylim())
        axis.set_yticks(major_ticks)
        axis.set_yticklabels(["%g" % value for value in major_ticks])
        axis.set_yticks(minor_ticks, minor=True)
        axis.set_yticklabels([], minor=True)
    axes[1].set_xscale("log")
    axes[1].set_xlim(data["completed_chunks"][0], planned_chunks)
    for axis in axes:
        axis.tick_params(axis="x", which="minor", length=4, width=0.8)
    figure.suptitle(species + " ionization convergence")
    figure.tight_layout()
    filename = simname + ".convergence.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename


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

    geometry_path = Path(simname + ".gdml")
    layers = read_layers(geometry_path)

    if Path(simname + ".ioni").is_file():
        try:
            direction_axes = get_histogram_axes(simname + "_h2_h2.dir.csv")
            position_axes = get_histogram_axes(simname + "_h2_h2.pos.csv")
            primary_energy = _read_raw_histogram(simname + "_h1_h1.1.csv", 7)
            direction = _read_raw_histogram(simname + "_h2_h2.dir.csv", 10)
            position = _read_raw_histogram(simname + "_h2_h2.pos.csv", 10)
            detector_ids, ionization = _read_response(simname + ".ioni")
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
                detector_ids,
                layers,
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
        detector_ids = None
        for quantity, title in zip(quantities, titles):
            response_file = "%s.%s%i" % (simname, quantity, phantom_id)
            if not Path(response_file).is_file():
                errors.append("%s results: missing %s" % (simname, response_file))
                continue
            try:
                response_detector_ids, response = _read_response(response_file)
            except Exception as error:
                errors.append("%s: %s" % (response_file, error))
                continue
            if detector_ids is None:
                detector_ids = response_detector_ids
            elif not np.array_equal(response_detector_ids, detector_ids):
                errors.append("%s: detector IDs do not match" % response_file)
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
                detector_ids,
                layers,
                filename,
            )
            filenames.append(filename)
        except Exception as error:
            errors.append("%s results: %s" % (simname, error))
    return filenames, errors


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Create quick-look PNG plots from the AtRIS inputs and result "
            "products already present in a run directory."
        ),
        epilog=(
            "Recognized products include prepared macros and geometry, binary "
            "or ASCII mode-0 interface records, mode-1 step traces, convergence "
            "tables, and post-processed proton and alpha responses. Missing "
            "product groups are skipped so partial runs can still be inspected. "
            "Existing PNG files with the generated names are replaced. This "
            "command does not run AtRIS, gather chunks, or post-process raw "
            "histograms."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        metavar="RUN_DIRECTORY",
        help="Run directory to inspect (default: current directory).",
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    run_directory = args.run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise SystemExit("Run directory does not exist: " + str(run_directory))

    previous_directory = Path.cwd()
    input_plots = []
    plotted = []
    errors = []
    logger.info("Starting plotting in %s", run_directory)
    try:
        os.chdir(run_directory)
        try:
            input_plots, input_errors = plot_inputs()
            errors.extend(input_errors)
        except Exception as error:
            errors.append("inputs: " + str(error))
        for simulation in ("protons", "alphas"):
            binary_path = Path(simulation + ".binary")
            ascii_path = Path(simulation + ".ascii")
            step_path = Path(simulation + ".steps.binary")
            if binary_path.is_file() or ascii_path.is_file():
                try:
                    plotted.append(plot_interface_output(simulation))
                except Exception as error:
                    errors.append(
                        "%s mode-0 output: %s" % (simulation, error)
                    )
            if step_path.is_file():
                try:
                    plotted.extend(plot_mode_one_output(simulation))
                except Exception as error:
                    errors.append(
                        "%s mode-1 output: %s" % (simulation, error)
                    )
            if Path(simulation + ".convergence.csv").is_file():
                try:
                    plotted.append(plot_convergence(simulation))
                except Exception as error:
                    errors.append(
                        "%s convergence: %s" % (simulation, error)
                    )
            if not _has_processed_output(simulation):
                logger.info(
                    "Skipping %s response plots: processed output not found",
                    simulation,
                )
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
        logger.warning("Could not plot %s", error)
    if input_plots:
        logger.info("Wrote input PNG plots to %s", run_directory)
        logger.debug("Input plots: %s", ", ".join(input_plots))
    if plotted:
        logger.info("Wrote PNG plots to %s", run_directory)
        logger.debug("Result plots: %s", ", ".join(plotted))
    elif not input_plots:
        logger.info("No processed simulation output found in %s", run_directory)


if __name__ == "__main__":
    main()
