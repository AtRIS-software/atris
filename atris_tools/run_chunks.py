"""Run incomplete entries from an AtRIS chunk plan."""

import argparse
from pathlib import Path
import subprocess
import time

from .gather import read_chunk_plan
from .phantoms import read_phantoms


def chunk_name(entry):
    """Return the output-prefix name for one chunk-plan entry."""
    simulation, seed1, seed2 = entry
    return "%s_%s_%s" % (simulation, seed1, seed2)


def select_entries(entries, entry=None, worker_index=0, worker_count=1):
    """Select one entry or the round-robin shard assigned to a worker."""
    if worker_count < 1:
        raise ValueError("Worker count must be at least 1")
    if worker_index < 0 or worker_index >= worker_count:
        raise ValueError(
            "Worker index must be between 0 and %i" % (worker_count - 1)
        )
    if entry is not None:
        if entry < 1 or entry > len(entries):
            raise ValueError("Chunk entry must be between 1 and %i" % len(entries))
        return [(entry, entries[entry - 1])]
    return [
        (line_number, plan_entry)
        for line_number, plan_entry in enumerate(entries, start=1)
        if (line_number - 1) % worker_count == worker_index
    ]


def incomplete_entry_numbers(run_directory):
    """Return one-based plan entries without completion markers."""
    run_directory = Path(run_directory).expanduser().resolve()
    entries = read_chunk_plan(run_directory)
    chunks_directory = run_directory / "chunks"
    return [
        line_number
        for line_number, plan_entry in enumerate(entries, start=1)
        if not (chunks_directory / (chunk_name(plan_entry) + ".COMPLETE")).is_file()
    ]


def run_chunks(
    run_directory,
    physics_list="FTFP_BERT_HP",
    mode=-1,
    entry=None,
    worker_index=0,
    worker_count=1,
    deadline=None,
    stop_before_end=0,
    clock=time.time,
):
    """Run incomplete chunks and mark each successful run as complete."""
    run_directory = Path(run_directory).expanduser().resolve()
    entries = read_chunk_plan(run_directory)
    selected_entries = select_entries(
        entries,
        entry=entry,
        worker_index=worker_index,
        worker_count=worker_count,
    )
    if stop_before_end < 0:
        raise ValueError("Stop-before-end interval cannot be negative")
    if stop_before_end and deadline is None:
        raise ValueError("Stop-before-end interval requires a job deadline")

    if worker_count > 1:
        print(
            "Worker %i/%i assigned %i chunk(s)."
            % (worker_index + 1, worker_count, len(selected_entries)),
            flush=True,
        )

    phantom_count = len(read_phantoms(run_directory))
    completed = 0
    for line_number, plan_entry in selected_entries:
        run_name = chunk_name(plan_entry)
        complete = run_directory / "chunks" / (run_name + ".COMPLETE")
        if complete.is_file():
            print(
                "Chunk %i/%i already complete: %s"
                % (line_number, len(entries), run_name)
            )
            continue

        if deadline is not None and clock() >= deadline - stop_before_end:
            print(
                "Worker %i/%i stopped before starting chunk %i/%i because "
                "the wall-time safety window has begun."
                % (worker_index + 1, worker_count, line_number, len(entries)),
                flush=True,
            )
            break

        log_path = run_directory / "chunks" / (run_name + ".log")
        print(
            "Starting chunk %i/%i: %s (log: %s)"
            % (line_number, len(entries), run_name, log_path),
            flush=True,
        )
        with log_path.open("w") as log:
            subprocess.run(
                [
                    "AtRIS",
                    physics_list,
                    str(Path("chunks") / run_name),
                    str(mode),
                    str(phantom_count),
                ],
                cwd=run_directory,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        complete.touch()
        completed += 1
        print(
            "Completed chunk %i/%i: %s" % (line_number, len(entries), run_name),
            flush=True,
        )

    return completed


def main():
    parser = argparse.ArgumentParser(
        description="Run incomplete entries from an AtRIS chunk plan."
    )
    parser.add_argument("run_directory", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--physics-list",
        default="FTFP_BERT_HP",
        help="Geant4 physics list (default: FTFP_BERT_HP).",
    )
    parser.add_argument(
        "--mode",
        type=int,
        default=-1,
        help="AtRIS output mode (default: -1).",
    )
    parser.add_argument(
        "--entry",
        type=int,
        help="Run only this one-based chunks.txt entry.",
    )
    parser.add_argument(
        "--worker-index",
        type=int,
        help="Zero-based worker rank (default: 0).",
    )
    parser.add_argument(
        "--worker-count",
        type=int,
        help="Total workers (default: 1).",
    )
    parser.add_argument(
        "--stop-before-end",
        type=int,
        default=0,
        metavar="SECONDS",
        help=(
            "Do not start another chunk within this many seconds of the "
            "configured job deadline."
        ),
    )
    parser.add_argument(
        "--deadline",
        type=float,
        metavar="UNIX_TIME",
        help="Optional absolute job deadline.",
    )
    parser.add_argument(
        "--check-complete",
        action="store_true",
        help="Exit successfully only when every chunks.txt entry is complete.",
    )
    args = parser.parse_args()

    if args.check_complete:
        incomplete = incomplete_entry_numbers(args.run_directory)
        if incomplete:
            preview = ", ".join(str(number) for number in incomplete[:20])
            if len(incomplete) > 20:
                preview += ", ..."
            print(
                "Chunk plan is incomplete: %i entry or entries remain (%s)."
                % (len(incomplete), preview)
            )
            return 1
        print("Chunk plan is complete.")
        return 0

    if args.worker_index is None and args.worker_count is None:
        worker_index, worker_count = 0, 1
    elif (args.worker_index is None) != (args.worker_count is None):
        parser.error("--worker-index and --worker-count must be supplied together")
    else:
        worker_index, worker_count = args.worker_index, args.worker_count

    completed = run_chunks(
        args.run_directory,
        physics_list=args.physics_list,
        mode=args.mode,
        entry=args.entry,
        worker_index=worker_index,
        worker_count=worker_count,
        deadline=args.deadline,
        stop_before_end=args.stop_before_end,
    )
    print("Completed %i new chunk(s)." % completed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
