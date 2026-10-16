"""Convergence statistics and reports for gathered atmospheric responses."""

import logging
import math

import numpy as np

from .file_io import atomic_text_output
from .psf import detector_geometry
logger = logging.getLogger(__name__)


CHANGE_FRACTION = 0.1
CONVERGENCE_COLUMNS = (
    "completed_chunks,primary_events,comparison_chunks,"
    "comparison_percent,ionization_change_percent,"
    "cell_change_p50_percent,cell_change_p90_percent,"
    "cell_relative_se_p50_percent,cell_relative_se_p90_percent"
)


def ionization_components(primary_energy, ionization):
    """Return primary counts and ionization sums for plotted detector cells."""
    primary_counts = primary_energy[1:-1]
    return primary_counts, ionization[1:-1, 2:-2].T


def ionization_response(primary_energy, ionization, geometry):
    """Return the ionization matrix displayed by the quick-look plot."""
    primary_counts, ionization_sum = ionization_components(
        primary_energy, ionization
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


def ionization_convergence_observer(
    run_directory, completed_count, primary_snapshots
):
    """Return an observer that calculates convergence after every chunk."""
    geometry, _ = detector_geometry(run_directory / "simulation.psf")
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
            primary_chunk, ionization_chunk.values
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
            ionization_total.values,
            geometry,
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
                    int(primary_total[1:-1].sum()),
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

    return observe, rows


def write_convergence(path, rows):
    """Write an ionization convergence table atomically."""
    with atomic_text_output(path) as output:
        output.write(CONVERGENCE_COLUMNS + "\n")
        np.savetxt(
            output,
            rows,
            delimiter=",",
            fmt=("%i", "%i", "%i") + ("%.17g",) * 6,
        )


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
