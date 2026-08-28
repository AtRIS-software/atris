"""Run incomplete entries from an AtRIS chunk plan."""

import argparse
import logging
import math
from pathlib import Path
import subprocess
import textwrap
import time

from .cli import add_logging_arguments, configure_logging
from .gather import read_chunk_plan
from .phantoms import read_phantoms


logger = logging.getLogger(__name__)

OUTPUT_MODES = ("response", "interface", "legacy-ascii")
OUTPUT_MODE_VALUES = {
    "response": "-1",
    "interface": "0",
    "legacy-ascii": "1",
}
OUTPUT_MODE_ALIASES = {
    "-1": "response",
    "0": "interface",
    "1": "legacy-ascii",
}


class HelpFormatter(argparse.HelpFormatter):
    """Use argparse wrapping without splitting words or option names."""

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(" ", text).strip()
        return textwrap.wrap(
            text,
            width,
            break_long_words=False,
            break_on_hyphens=False,
        )

    def _fill_text(self, text, width, indent):
        rendered = []
        for line in text.splitlines():
            if not line.strip():
                rendered.append("")
                continue
            leading_space = line[: len(line) - len(line.lstrip())]
            line_indent = indent + leading_space
            line = self._whitespace_matcher.sub(" ", line).strip()
            rendered.append(
                textwrap.fill(
                    line,
                    width,
                    initial_indent=line_indent,
                    subsequent_indent=line_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        return "\n".join(rendered)


def normalize_output_mode(value):
    """Return a named AtRIS output mode, accepting old numeric aliases."""
    value = str(value)
    value = OUTPUT_MODE_ALIASES.get(value, value)
    if value not in OUTPUT_MODES:
        raise ValueError(
            "output mode must be response, interface, or legacy-ascii"
        )
    return value


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
    mode="response",
    entry=None,
    worker_index=0,
    worker_count=1,
    deadline=None,
    stop_before_end=0,
    clock=time.time,
):
    """Run incomplete chunks and mark each successful run as complete."""
    run_directory = Path(run_directory).expanduser().resolve()
    mode = OUTPUT_MODE_VALUES[normalize_output_mode(mode)]
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

    pending_count = sum(
        not (
            run_directory
            / "chunks"
            / (chunk_name(plan_entry) + ".COMPLETE")
        ).is_file()
        for _, plan_entry in selected_entries
    )
    logger.info(
        "Worker %i/%i has %i incomplete chunks among %i assigned",
        worker_index + 1,
        worker_count,
        pending_count,
        len(selected_entries),
    )
    milestone = max(1, math.ceil(pending_count / 7))

    phantom_count = len(read_phantoms(run_directory))
    completed = 0
    for line_number, plan_entry in selected_entries:
        run_name = chunk_name(plan_entry)
        complete = run_directory / "chunks" / (run_name + ".COMPLETE")
        if complete.is_file():
            logger.debug(
                "Chunk %i/%i already complete: %s",
                line_number,
                len(entries),
                run_name,
            )
            continue

        if deadline is not None and clock() >= deadline - stop_before_end:
            logger.info(
                "Worker %i/%i stopped before starting chunk %i/%i because "
                "the wall-time safety window has begun",
                worker_index + 1,
                worker_count,
                line_number,
                len(entries),
            )
            break

        log_path = run_directory / "chunks" / (run_name + ".log")
        logger.debug(
            "Starting chunk %i/%i: %s (log: %s)",
            line_number,
            len(entries),
            run_name,
            log_path,
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
        logger.debug(
            "Completed chunk %i/%i: %s",
            line_number,
            len(entries),
            run_name,
        )
        if completed % milestone == 0 or completed == pending_count:
            logger.info(
                "Worker %i/%i completed %i/%i pending chunks",
                worker_index + 1,
                worker_count,
                completed,
                pending_count,
            )

    return completed


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run the incomplete entries assigned to one worker from an AtRIS "
            "chunk plan, marking each successful chunk complete."
        ),
        formatter_class=HelpFormatter,
        epilog=(
            "The command reads chunks.txt and phantoms.txt, skips entries with "
            "an existing .COMPLETE marker, and runs selected entries "
            "sequentially. Worker coordinates select a collision-free shard; "
            "they do not launch workers or control Geant4 threads. A deadline "
            "is checked only before a chunk starts and never interrupts a "
            "running chunk. Failed chunks are left incomplete. The response mode "
            "writes the normal "
            "histogram workflow; interface additionally writes particle "
            "crossings, and legacy-ascii retains the historical "
            "ASCII mode. This command does not gather or post-process results."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        metavar="RUN_DIRECTORY",
        help="Scattered run directory (default: current directory).",
    )
    atris_options = parser.add_argument_group("AtRIS execution options")
    atris_options.add_argument(
        "--physics-list",
        default="FTFP_BERT_HP",
        metavar="NAME",
        help="Geant4 reference physics list passed to AtRIS (default: FTFP_BERT_HP).",
    )
    atris_options.add_argument(
        "--mode",
        type=normalize_output_mode,
        choices=OUTPUT_MODES,
        default="response",
        help=(
            "AtRIS output mode: response writes the normal histograms; "
            "interface also writes binary interface records; legacy-ascii "
            "selects the historical ASCII mode (default: response)."
        ),
    )
    chunk_options = parser.add_argument_group("Chunk plan and worker options")
    chunk_options.add_argument(
        "--entry",
        type=int,
        metavar="NUMBER",
        help=(
            "Run only this one-based chunks.txt entry instead of a worker "
            "shard. A completed entry is still skipped."
        ),
    )
    chunk_options.add_argument(
        "--worker-index",
        type=int,
        metavar="INDEX",
        help=(
            "Zero-based rank used to select this worker's round-robin shard; "
            "must be supplied with --worker-count (default: 0)."
        ),
    )
    chunk_options.add_argument(
        "--worker-count",
        type=int,
        metavar="COUNT",
        help=(
            "Number of externally launched workers sharing the plan; must be "
            "supplied with --worker-index (default: 1)."
        ),
    )
    chunk_options.add_argument(
        "--stop-before-end",
        type=int,
        default=0,
        metavar="SECONDS",
        help=(
            "Do not start another chunk within SECONDS of --deadline "
            "(default: 0)."
        ),
    )
    chunk_options.add_argument(
        "--deadline",
        type=float,
        metavar="UNIX_TIME",
        help=(
            "Absolute Unix timestamp at which the external allocation ends; "
            "used only with --stop-before-end."
        ),
    )
    chunk_options.add_argument(
        "--check-complete",
        action="store_true",
        help=(
            "Do not run anything; return success only when every chunks.txt "
            "entry has a completion marker."
        ),
    )
    logging_options = parser.add_argument_group("Logging options")
    add_logging_arguments(logging_options)

    parser.add_argument_group(
        "Examples",
        description=(
            "atris-run runs/earth\n"
            "  Run every incomplete chunk sequentially.\n"
            "\n"
            "G4FORCENUMBEROFTHREADS=7 atris-run runs/earth \\\n"
            "  --worker-index 2 --worker-count 11 \\\n"
            "  --deadline \"$JOB_END_TIME\" --stop-before-end 1800\n"
            "  Run worker index 2's round-robin shard of an 11-worker pool with "
            "seven Geant4 threads. It does not start a new chunk during the "
            "allocation's final 30 minutes. Launch the other worker indices "
            "externally.\n"
            "\n"
            "atris-run runs/earth --entry 17\n"
            "  Run only plan entry 17 unless it is already complete.\n"
            "\n"
            "atris-run runs/earth --check-complete\n"
            "  Check whether every planned chunk has a completion marker."
        ),
    )
    args = parser.parse_args()
    configure_logging(args.log_level)

    if args.check_complete:
        incomplete = incomplete_entry_numbers(args.run_directory)
        if incomplete:
            preview = ", ".join(str(number) for number in incomplete[:20])
            if len(incomplete) > 20:
                preview += ", ..."
            logger.warning(
                "Chunk plan is incomplete: %i entries remain (%s)",
                len(incomplete),
                preview,
            )
            return 1
        logger.info("Chunk plan is complete")
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
    logger.info("Completed %i new chunks", completed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
