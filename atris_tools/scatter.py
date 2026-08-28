"""Prepare independently seeded AtRIS chunks from ordinary macros."""

import argparse
from pathlib import Path
import random


SPECIES = ("protons", "alphas")


def chunk_macro(source, chunks):
    lines = source.read_text().splitlines(keepends=True)
    beam_lines = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("/run/beamOn ")
    ]
    if len(beam_lines) != 1:
        raise ValueError(
            "%s must contain exactly one /run/beamOn command" % source
        )

    beam_index = beam_lines[0]
    fields = lines[beam_index].split()
    if len(fields) != 2:
        raise ValueError("Invalid /run/beamOn command in %s" % source)
    try:
        total_events = int(fields[1])
    except ValueError as error:
        raise ValueError("Invalid /run/beamOn command in %s" % source) from error
    if total_events < 1:
        raise ValueError(
            "/run/beamOn must request at least one event in %s" % source
        )

    events_per_chunk = (total_events + chunks - 1) // chunks
    newline = "\n" if lines[beam_index].endswith("\n") else ""
    stripped_line = lines[beam_index].lstrip()
    indentation_length = len(lines[beam_index]) - len(stripped_line)
    indentation = lines[beam_index][:indentation_length]
    lines[beam_index] = "%s/run/beamOn %i%s" % (
        indentation,
        events_per_chunk,
        newline,
    )
    contents = "".join(
        line
        for line in lines
        if not line.lstrip().startswith("/random/setSeeds ")
    )
    return contents, total_events, events_per_chunk


def chunk_plan(chunks, rng):
    used_pairs = set()
    lines = []
    for species in SPECIES:
        for _ in range(chunks):
            while True:
                seeds = (rng.randint(31, 999999), rng.randint(31, 999999))
                if seeds not in used_pairs:
                    break
            used_pairs.add(seeds)
            lines.append("%s %06i %06i\n" % (species, seeds[0], seeds[1]))
    return lines


def scatter(run_directory, chunks, random_seed=None):
    if chunks < 1:
        raise ValueError("chunks must be at least 1")

    run_directory = Path(run_directory).expanduser().resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))

    plan_path = run_directory / "chunks.txt"
    chunks_directory = run_directory / "chunks"
    if plan_path.exists():
        raise FileExistsError("Chunk plan already exists: " + str(plan_path))
    if chunks_directory.exists():
        if not chunks_directory.is_dir():
            raise FileExistsError(
                "Chunk output path is not a directory: " + str(chunks_directory)
            )
        if any(chunks_directory.iterdir()):
            raise FileExistsError(
                "Chunk output directory is not empty: " + str(chunks_directory)
            )

    chunk_macros = {}
    rounded_totals = []
    for species in SPECIES:
        source = run_directory / (species + ".mac")
        destination = run_directory / (species + ".chunk.mac")
        if not source.is_file():
            raise FileNotFoundError("Ordinary macro does not exist: " + str(source))
        if destination.exists():
            raise FileExistsError("Chunk macro already exists: " + str(destination))
        contents, total_events, events_per_chunk = chunk_macro(source, chunks)
        chunk_macros[destination] = contents
        actual_events = events_per_chunk * chunks
        if actual_events != total_events:
            rounded_totals.append(
                (species, total_events, actual_events, events_per_chunk)
            )

    rng = random.Random(random_seed)
    plan_lines = chunk_plan(chunks, rng)
    chunks_directory.mkdir(exist_ok=True)
    for destination, contents in chunk_macros.items():
        destination.write_text(contents)
    with plan_path.open("x") as plan:
        plan.writelines(plan_lines)
    for species, requested, actual, per_chunk in rounded_totals:
        print(
            "INFO: Rounded %s from %i requested events to %i across %i chunks "
            "(%i events per chunk)."
            % (species, requested, actual, chunks, per_chunk)
        )

    return run_directory


def main():
    parser = argparse.ArgumentParser(
        description="Prepare independently seeded chunks from ordinary AtRIS macros."
    )
    parser.add_argument("run_directory", nargs="?", default=".")
    parser.add_argument(
        "--chunks",
        type=int,
        required=True,
        help="Number of chunks to create for each particle species.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Seed used to generate reproducible chunk seed pairs.",
    )
    args = parser.parse_args()

    run_directory = scatter(args.run_directory, args.chunks, args.random_seed)
    print(
        "Created %i proton chunks and %i alpha chunks (%i total) in %s"
        % (args.chunks, args.chunks, args.chunks * 2, run_directory)
    )


if __name__ == "__main__":
    main()
