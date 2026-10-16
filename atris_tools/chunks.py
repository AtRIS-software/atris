"""Chunk-plan naming, completion markers and progress reporting."""

import logging
logger = logging.getLogger(__name__)


ETA_COMPLETION_WINDOW = 20


def read_plan(path):
    """Read simulation and seed triples from a chunk-plan file."""
    entries = []
    with path.open() as plan:
        for line_number, line in enumerate(plan, start=1):
            fields = line.split()
            if len(fields) != 3:
                raise ValueError("Invalid %s line %i" % (path.name, line_number))
            simulation, seed1, seed2 = fields
            entries.append((simulation, seed1, seed2))
    return entries


def read_chunk_plan(run_directory):
    return read_plan(run_directory / "chunks.txt")


def chunk_name(entry):
    """Return the output-prefix name for one chunk-plan entry."""
    return "%s_%s_%s" % entry


def complete_entries(run_directory, entries, simulation):
    chunks_directory = run_directory / "chunks"
    return [
        entry
        for entry in entries
        if entry[0] == simulation
        and (
            chunks_directory
            / (chunk_name(entry) + ".COMPLETE")
        ).is_file()
    ]


def chunk_progress(run_directory, entries, simulations):
    """Return completion counts, interval, and estimated remaining seconds."""
    simulations = set(simulations)
    markers = []
    total = 0
    chunks_directory = run_directory / "chunks"
    for entry in entries:
        simulation = entry[0]
        if simulation not in simulations:
            continue
        total += 1
        marker = chunks_directory / (chunk_name(entry) + ".COMPLETE")
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
