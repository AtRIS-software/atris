import argparse
import logging
import os
import shutil
from pathlib import Path

from .cli import add_logging_arguments, configure_logging


logger = logging.getLogger(__name__)


def read_phantoms(run_directory):
    metadata_path = Path(run_directory) / "phantoms.txt"
    if not metadata_path.exists():
        return []

    phantoms = []
    with metadata_path.open() as metadata_file:
        for line_number, line in enumerate(metadata_file, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            columns = line.split()
            if len(columns) != 4:
                raise ValueError(
                    "Expected ID, file stem, mass, and area at "
                    + str(metadata_path)
                    + ":"
                    + str(line_number)
                )
            try:
                phantom_id = int(columns[0])
                mass = float(columns[2])
                area = float(columns[3])
            except ValueError as error:
                raise ValueError(
                    "Invalid phantom ID, mass, or area at "
                    + str(metadata_path)
                    + ":"
                    + str(line_number)
                ) from error
            phantoms.append(
                {
                    "id": phantom_id,
                    "stem": columns[1],
                    "mass": mass,
                    "area": area,
                }
            )

    phantoms.sort(key=lambda phantom: phantom["id"])
    ids = [phantom["id"] for phantom in phantoms]
    if ids != list(range(len(phantoms))):
        raise ValueError("Phantom IDs must be unique and contiguous from 0")
    return phantoms


def find_phantom_file(filename, run_directory, archive):
    path = Path(filename)
    candidates = [path] if path.is_absolute() else [run_directory / path]
    if not path.is_absolute() and archive is not None:
        candidates.append(archive / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Phantom file does not exist: " + filename)


def stage_phantoms(run_directory, archive=None, copy=False):
    run_directory = Path(run_directory).resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))
    if archive is not None:
        archive = Path(archive).resolve()

    phantoms = read_phantoms(run_directory)
    operations = []
    conflicts = []
    for phantom in phantoms:
        phantom_id = phantom["id"]
        stem = phantom["stem"]
        radiation = find_phantom_file(
            stem + "_response.txt", run_directory, archive
        )
        counting = find_phantom_file(
            stem + "_counting.txt", run_directory, archive
        )
        radiation_destination = run_directory / (
            "radiation_phantom" + str(phantom_id) + ".txt"
        )
        counting_destination = run_directory / (
            "counting_phantom" + str(phantom_id) + ".txt"
        )
        operations.extend(
            (
                (radiation, radiation_destination),
                (counting, counting_destination),
            )
        )

    pending = []
    for source, destination in operations:
        if not os.path.lexists(destination):
            pending.append((source, destination))
        elif destination.is_file() and destination.resolve() == source:
            continue
        else:
            conflicts.append(str(destination))
    if conflicts:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(conflicts))

    created = []
    try:
        for source, destination in pending:
            created.append(destination)
            if copy:
                shutil.copy2(source, destination)
                logger.debug("Copied %s to %s", source, destination)
            else:
                destination.symlink_to(os.path.relpath(source, run_directory))
                logger.debug("Linked %s to %s", destination, source)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    return len(phantoms)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Stage the phantom response and counting tables selected by "
            "phantoms.txt under the numbered filenames expected by AtRIS."
        ),
        epilog=(
            "Each phantoms.txt row must contain ID, file stem, mass, and area; "
            "IDs must be contiguous from zero. The command does not create "
            "phantom responses or change phantoms.txt. Existing matching links "
            "are accepted, while conflicting destination files are not "
            "overwritten."
        ),
    )
    parser.add_argument(
        "run_directory",
        metavar="RUN_DIRECTORY",
        help="Run directory containing phantoms.txt.",
    )
    parser.add_argument(
        "--archive",
        metavar="DIRECTORY",
        help=(
            "Directory containing the named phantom tables. Files in the run "
            "directory are checked first; the default archive is "
            "$ATRIS_ROOT/phantoms when ATRIS_ROOT is set. Without either, only "
            "the run directory is searched."
        ),
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help=(
            "Copy response files into the run directory instead of creating "
            "relative symbolic links."
        ),
    )
    add_logging_arguments(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    archive = args.archive
    if archive is None:
        atris_root = os.environ.get("ATRIS_ROOT")
        if atris_root:
            archive = os.path.join(atris_root, "phantoms")

    count = stage_phantoms(
        args.run_directory,
        archive,
        copy=args.copy,
    )
    if count == 0:
        logger.info("No phantoms to stage")
    else:
        method = "copied files" if args.copy else "relative symbolic links"
        logger.info("Staged %i phantoms using %s", count, method)


if __name__ == "__main__":
    main()
