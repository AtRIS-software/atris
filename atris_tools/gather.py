#!/usr/bin/env python3
"""Gather completed AtRIS repetitions into canonical histogram files."""

import argparse
import logging
import math
import os
from pathlib import Path
import tempfile

import numpy as np

from .postprocess import process_psf


PLANE_SUM_PREFIX = "#planes_Sxyw "
ETA_COMPLETION_WINDOW = 20
CHANGE_FRACTION = 0.1
CONVERGENCE_COLUMNS = (
    "completed_chunks,primary_events,comparison_chunks,"
    "comparison_percent,ionization_change_percent,"
    "cell_change_p50_percent,cell_change_p90_percent,"
    "cell_relative_se_p50_percent,cell_relative_se_p90_percent"
)
logger = logging.getLogger(__name__)


def read_chunk_plan(run_directory):
    entries = []
    plan_path = run_directory / "chunks.txt"
    with plan_path.open() as plan:
        for line_number, line in enumerate(plan, start=1):
            fields = line.split()
            if len(fields) != 3:
                raise ValueError("Invalid chunks.txt line %i" % line_number)
            simulation, seed1, seed2 = fields
            entries.append((simulation, seed1, seed2))
    return entries


def completed_prefixes(run_directory, entries, simulation):
    chunks_directory = run_directory / "chunks"
    prefixes = []
    for entry_simulation, seed1, seed2 in entries:
        if entry_simulation != simulation:
            continue
        prefix = chunks_directory / (simulation + "_" + seed1 + "_" + seed2)
        if prefix.with_name(prefix.name + ".COMPLETE").is_file():
            prefixes.append(prefix)
    return prefixes


def chunk_progress(run_directory, entries, simulations):
    """Return completion counts, interval, and estimated remaining seconds."""
    simulations = set(simulations)
    markers = []
    total = 0
    chunks_directory = run_directory / "chunks"
    for simulation, seed1, seed2 in entries:
        if simulation not in simulations:
            continue
        total += 1
        marker = chunks_directory / (
            "%s_%s_%s.COMPLETE" % (simulation, seed1, seed2)
        )
        if marker.is_file():
            markers.append(marker)

    completed = len(markers)
    if completed < 2:
        remaining_seconds = 0 if completed == total else None
        return completed, total, None, remaining_seconds

    completion_times = sorted(marker.stat().st_mtime for marker in markers)
    recent_times = completion_times[-ETA_COMPLETION_WINDOW:]
    seconds_per_chunk = (recent_times[-1] - recent_times[0]) / (
        len(recent_times) - 1
    )
    return (
        completed,
        total,
        seconds_per_chunk,
        seconds_per_chunk * (total - completed),
    )


def format_duration(seconds):
    """Format a duration for a compact progress message."""
    seconds = max(0, round(seconds))
    days, seconds = divmod(seconds, 24 * 60 * 60)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return "%id %ih" % (days, hours)
    if hours:
        return "%ih %im" % (hours, minutes)
    if minutes:
        return "%im %is" % (minutes, seconds)
    return "%is" % seconds


def log_chunk_progress(run_directory, entries, simulations):
    """Log chunk completion progress and an ETA when one is available."""
    completed, total, completion_interval, remaining_seconds = chunk_progress(
        run_directory, entries, simulations
    )
    if completed == total:
        if completion_interval is None:
            logger.info("Chunk progress: %i/%i complete.", completed, total)
        else:
            logger.info(
                "Chunk progress: %i/%i complete; average completion interval %s.",
                completed,
                total,
                format_duration(completion_interval),
            )
    elif remaining_seconds is None:
        logger.info(
            "Chunk progress: %i/%i complete; ETA available after two completions.",
            completed,
            total,
        )
    else:
        logger.info(
            "Chunk progress: %i/%i complete; average completion interval %s; "
            "estimated time remaining %s.",
            completed,
            total,
            format_duration(completion_interval),
            format_duration(remaining_seconds),
        )


def read_histogram(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    header = lines[:column_index]
    columns = lines[column_index]
    data = np.loadtxt(path, delimiter=",", skiprows=column_index + 1)
    return header, columns, np.atleast_2d(data)


def comparable_header(header):
    return [line for line in header if not line.startswith(PLANE_SUM_PREFIX)]


def plane_sum(header):
    for line in header:
        if line.startswith(PLANE_SUM_PREFIX):
            return float(line[len(PLANE_SUM_PREFIX):])
    return None


def write_histogram(path, header, columns, data, total_plane_sum):
    output_header = list(header)
    if total_plane_sum is not None:
        for index, line in enumerate(output_header):
            if line.startswith(PLANE_SUM_PREFIX):
                output_header[index] = PLANE_SUM_PREFIX + "%.17g" % total_plane_sum

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_name = output.name
            for line in output_header:
                output.write(line + "\n")
            output.write(columns + "\n")
            formats = ["%.0f"] + ["%.17g"] * (data.shape[1] - 1)
            np.savetxt(output, data, delimiter=",", fmt=formats)
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def combine_histograms(source_paths, snapshot_counts=(), observe=None):
    snapshot_counts = set(snapshot_counts)
    first_header, first_columns, total = read_histogram(source_paths[0])
    total_plane_sum = plane_sum(first_header)
    snapshots = {1: total.copy()} if 1 in snapshot_counts else {}
    if observe is not None:
        observe(1, total, total)

    for source_number, source_path in enumerate(source_paths[1:], start=2):
        header, columns, data = read_histogram(source_path)
        if comparable_header(header) != comparable_header(first_header):
            raise ValueError("Histogram headers differ: " + str(source_path))
        if columns != first_columns or data.shape != total.shape:
            raise ValueError("Histogram shape differs: " + str(source_path))
        total += data
        current_plane_sum = plane_sum(header)
        if (total_plane_sum is None) != (current_plane_sum is None):
            raise ValueError("Histogram headers differ: " + str(source_path))
        if total_plane_sum is not None:
            total_plane_sum += current_plane_sum
        if source_number in snapshot_counts:
            snapshots[source_number] = total.copy()
        if observe is not None:
            observe(source_number, data, total)

    return first_header, first_columns, total, total_plane_sum, snapshots


def gather_histogram(source_paths, destination):
    header, columns, total, total_plane_sum, _ = combine_histograms(source_paths)

    write_histogram(destination, header, columns, total, total_plane_sum)
    return total


def ionization_components(primary_energy, ionization, detector_count):
    """Return primary counts and ionization sums for plotted detector cells."""
    primary_counts = primary_energy[1:-1, 0]
    ionization_sum = ionization[:, 1].reshape(
        (detector_count + 2, primary_counts.size + 2)
    )
    return primary_counts, ionization_sum[2:-2, 1:-1]


def ionization_response(primary_energy, ionization, geometry, detector_count):
    """Return the ionization matrix displayed by the quick-look plot."""
    primary_counts, ionization_sum = ionization_components(
        primary_energy, ionization, detector_count
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        response = ionization_sum / primary_counts[None, :]
        response = response / geometry["volume/cm3"][1:-1, None]
    return response


def fractional_change(previous, current):
    """Return symmetric fractional change between two nonnegative arrays."""
    previous = np.nan_to_num(previous, nan=0.0, posinf=0.0, neginf=0.0)
    current = np.nan_to_num(current, nan=0.0, posinf=0.0, neginf=0.0)
    denominator = np.sum(np.abs(previous) + np.abs(current))
    if denominator == 0:
        return 0.0
    return np.sum(np.abs(current - previous)) / denominator


def cell_change_percentiles(previous, current):
    """Return median and 90th-percentile fractional changes across cells."""
    previous = np.nan_to_num(previous, nan=0.0, posinf=0.0, neginf=0.0)
    current = np.nan_to_num(current, nan=0.0, posinf=0.0, neginf=0.0)
    denominator = np.abs(previous) + np.abs(current)
    changed = denominator > 0
    values = np.abs(current[changed] - previous[changed]) / denominator[changed]
    return finite_percentiles(values)


def finite_percentiles(values):
    """Return median and 90th percentile after excluding undefined cells."""
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    if not values.size:
        return np.array([np.nan, np.nan])
    return np.percentile(values, (50, 90))


def change_reference_count(completed_count):
    """Return the chunk count before the final comparison fraction."""
    if completed_count < 2:
        return None
    comparison_count = max(1, math.ceil(CHANGE_FRACTION * completed_count))
    return completed_count - comparison_count


def combine_ionization_histograms(
    run_directory, source_paths, primary_snapshots
):
    """Combine ionization files and calculate convergence after every chunk."""
    geometry, detector_count = process_psf(run_directory / "simulation.psf")
    completed_count = len(source_paths)
    references = {
        count: change_reference_count(count)
        for count in range(2, completed_count + 1)
    }
    last_use = {}
    for count, reference in references.items():
        last_use[reference] = count

    stored_responses = {}
    rows = []
    weights = None
    mean = None
    squared_residuals = None
    contributing_chunks = None

    def observe(count, ionization_chunk, ionization_total):
        nonlocal weights, mean, squared_residuals, contributing_chunks
        primary_total = primary_snapshots[count]
        if count == 1:
            primary_chunk = primary_total
        else:
            primary_chunk = primary_total - primary_snapshots[count - 1]

        chunk_counts, chunk_sum = ionization_components(
            primary_chunk, ionization_chunk, detector_count
        )
        if weights is None:
            weights = np.zeros(chunk_counts.shape)
            mean = np.zeros(chunk_sum.shape)
            squared_residuals = np.zeros(chunk_sum.shape)
            contributing_chunks = np.zeros(chunk_counts.shape, dtype=int)

        chunk_mean = np.zeros(chunk_sum.shape)
        np.divide(
            chunk_sum,
            chunk_counts[None, :],
            out=chunk_mean,
            where=chunk_counts[None, :] > 0,
        )
        new_weights = weights + chunk_counts
        delta = chunk_mean - mean
        fraction = np.zeros(chunk_counts.shape)
        np.divide(
            chunk_counts,
            new_weights,
            out=fraction,
            where=new_weights > 0,
        )
        new_mean = mean + delta * fraction[None, :]
        squared_residuals += (
            chunk_counts[None, :] * delta * (chunk_mean - new_mean)
        )
        contributing_chunks += chunk_counts > 0
        weights = new_weights
        mean = new_mean

        current = ionization_response(
            primary_total,
            ionization_total,
            geometry,
            detector_count,
        )
        if count >= 2:
            reference_count = references[count]
            reference = stored_responses[reference_count]
            comparison_chunks = count - reference_count
            cell_change = 100.0 * cell_change_percentiles(
                reference, current
            )
            with np.errstate(divide="ignore", invalid="ignore"):
                variance = np.maximum(squared_residuals, 0.0) / (
                    contributing_chunks - 1
                )[None, :]
                standard_error = np.sqrt(variance / weights[None, :])
                relative_error = standard_error / np.abs(mean)
            cell_uncertainty = 100.0 * finite_percentiles(relative_error)
            rows.append(
                (
                    count,
                    int(primary_total[1:-1, 0].sum()),
                    comparison_chunks,
                    100.0 * comparison_chunks / count,
                    100.0 * fractional_change(reference, current),
                    cell_change[0],
                    cell_change[1],
                    cell_uncertainty[0],
                    cell_uncertainty[1],
                )
            )
            if last_use[reference_count] == count:
                del stored_responses[reference_count]
        if count in last_use:
            stored_responses[count] = current

    header, columns, total, total_plane_sum, _ = combine_histograms(
        source_paths, observe=observe
    )
    return header, columns, total, total_plane_sum, rows


def write_convergence(path, rows):
    """Write an ionization convergence table atomically."""
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_name = output.name
            output.write(CONVERGENCE_COLUMNS + "\n")
            np.savetxt(
                output,
                rows,
                delimiter=",",
                fmt=("%i", "%i", "%i") + ("%.17g",) * 6,
            )
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def log_ionization_change(simulation, row):
    """Report the final ionization convergence row."""
    completed_count, _, comparison_chunks, comparison_percent, change = row[:5]
    species = {"protons": "Proton", "alphas": "Alpha"}[simulation]
    logger.info(
        "%s ionization change after final %i of %i completed chunks "
        "(%.1f%%): %.2f%%",
        species,
        comparison_chunks,
        completed_count,
        comparison_percent,
        change,
    )


def gather_simulation(run_directory, entries, simulation):
    prefixes = completed_prefixes(run_directory, entries, simulation)
    if not prefixes:
        logger.info("No completed %s runs to gather", simulation)
        return 0
    logger.info(
        "Gathering %s from %i completed %s...",
        simulation,
        len(prefixes),
        "chunk" if len(prefixes) == 1 else "chunks",
    )

    first_prefix = prefixes[0]
    histogram_paths = sorted(first_prefix.parent.glob(first_prefix.name + "_*.csv"))
    if not histogram_paths:
        raise FileNotFoundError("Completed run has no histogram files: " + str(first_prefix))

    paths_by_suffix = {}
    for first_path in histogram_paths:
        suffix = first_path.name[len(first_prefix.name):]
        source_paths = [prefix.parent / (prefix.name + suffix) for prefix in prefixes]
        for source_path in source_paths:
            if not source_path.is_file():
                raise FileNotFoundError("Missing histogram from completed run: " + str(source_path))
        paths_by_suffix[suffix] = source_paths

    primary_events = 0
    primary_snapshots = None
    primary_suffix = "_h1_h1.1.csv"
    if primary_suffix in paths_by_suffix:
        header, columns, total, total_plane_sum, primary_snapshots = (
            combine_histograms(
                paths_by_suffix.pop(primary_suffix),
                range(1, len(prefixes) + 1),
            )
        )
        write_histogram(
            run_directory / (simulation + primary_suffix),
            header,
            columns,
            total,
            total_plane_sum,
        )
        primary_events = int(total[:, 0].sum())

    convergence = []
    ionization_suffix = "_h2_h2.ion.csv"
    if ionization_suffix in paths_by_suffix and primary_snapshots is not None:
        header, columns, total, total_plane_sum, convergence = (
            combine_ionization_histograms(
                run_directory,
                paths_by_suffix.pop(ionization_suffix),
                primary_snapshots,
            )
        )
        write_histogram(
            run_directory / (simulation + ionization_suffix),
            header,
            columns,
            total,
            total_plane_sum,
        )

    for suffix, source_paths in paths_by_suffix.items():
        gather_histogram(
            source_paths, run_directory / (simulation + suffix)
        )

    logger.info(
        "Gathered %i completed %s runs containing %i primary events",
        len(prefixes),
        simulation,
        primary_events,
    )
    if convergence:
        write_convergence(
            run_directory / (simulation + ".convergence.csv"), convergence
        )
        log_ionization_change(simulation, convergence[-1])
    return len(prefixes)


def main():
    parser = argparse.ArgumentParser(
        description="Gather completed AtRIS repetitions into canonical histogram files."
    )
    parser.add_argument("run_directory", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("simulations", nargs="*", default=("protons", "alphas"))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_directory = args.run_directory.expanduser().resolve()
    logger.info("Starting gather in %s", run_directory)
    entries = read_chunk_plan(run_directory)
    for simulation in args.simulations:
        gather_simulation(run_directory, entries, simulation)
    log_chunk_progress(run_directory, entries, args.simulations)


if __name__ == "__main__":
    main()
