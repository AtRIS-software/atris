"""Prepare independently seeded AtRIS chunks from ordinary macros."""

import argparse
from pathlib import Path
import random


SPECIES = ("protons", "alphas")


def chunk_macro(source):
    lines = source.read_text().splitlines(keepends=True)
    return "".join(
        line for line in lines
        if not line.lstrip().startswith("/random/setSeeds ")
    )


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
    for species in SPECIES:
        source = run_directory / (species + ".mac")
        destination = run_directory / (species + ".chunk.mac")
        if not source.is_file():
            raise FileNotFoundError("Ordinary macro does not exist: " + str(source))
        if destination.exists():
            raise FileExistsError("Chunk macro already exists: " + str(destination))
        chunk_macros[destination] = chunk_macro(source)

    rng = random.Random(random_seed)
    plan_lines = chunk_plan(chunks, rng)
    chunks_directory.mkdir(exist_ok=True)
    for destination, contents in chunk_macros.items():
        destination.write_text(contents)
    with plan_path.open("x") as plan:
        plan.writelines(plan_lines)

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
