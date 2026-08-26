#!/usr/bin/env python3
"""Gather completed AtRIS repetitions into canonical histogram files."""

import argparse
import os
from pathlib import Path
import tempfile

import numpy as np


PLANE_SUM_PREFIX = "#planes_Sxyw "


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


def gather_histogram(source_paths, destination):
    first_header, first_columns, total = read_histogram(source_paths[0])
    total_plane_sum = plane_sum(first_header)

    for source_path in source_paths[1:]:
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

    write_histogram(destination, first_header, first_columns, total, total_plane_sum)
    return total


def gather_simulation(run_directory, entries, simulation):
    prefixes = completed_prefixes(run_directory, entries, simulation)
    if not prefixes:
        print("No completed %s runs to gather" % simulation)
        return 0

    first_prefix = prefixes[0]
    histogram_paths = sorted(first_prefix.parent.glob(first_prefix.name + "_*.csv"))
    if not histogram_paths:
        raise FileNotFoundError("Completed run has no histogram files: " + str(first_prefix))

    primary_events = 0
    for first_path in histogram_paths:
        suffix = first_path.name[len(first_prefix.name):]
        source_paths = [prefix.parent / (prefix.name + suffix) for prefix in prefixes]
        for source_path in source_paths:
            if not source_path.is_file():
                raise FileNotFoundError("Missing histogram from completed run: " + str(source_path))
        total = gather_histogram(source_paths, run_directory / (simulation + suffix))
        if suffix == "_h1_h1.1.csv":
            primary_events = int(total[:, 0].sum())

    print(
        "Gathered %i completed %s runs containing %i primary events"
        % (len(prefixes), simulation, primary_events)
    )
    return len(prefixes)


def main():
    parser = argparse.ArgumentParser(
        description="Gather completed AtRIS repetitions into canonical histogram files."
    )
    parser.add_argument("run_directory", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("simulations", nargs="*", default=("protons", "alphas"))
    args = parser.parse_args()

    run_directory = args.run_directory.expanduser().resolve()
    entries = read_chunk_plan(run_directory)
    for simulation in args.simulations:
        gather_simulation(run_directory, entries, simulation)


if __name__ == "__main__":
    main()
