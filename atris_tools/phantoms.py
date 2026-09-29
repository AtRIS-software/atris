import argparse
import logging
import os
import shutil
from pathlib import Path

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)


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
    copy_operations = []
    link_operations = []
    conflicts = []
    for phantom in phantoms:
        phantom_id = phantom["id"]
        stem = phantom["stem"]
        filenames = (
            (
                stem + "_response.txt",
                "radiation_phantom" + str(phantom_id) + ".txt",
            ),
            (
                stem + "_counting.txt",
                "counting_phantom" + str(phantom_id) + ".txt",
            ),
        )
        for filename, staged_filename in filenames:
            source = find_phantom_file(filename, run_directory, archive)
            staged_source = source
            if copy:
                staged_source = run_directory / Path(filename).name
                if source != staged_source:
                    copy_operations.append((source, staged_source))
            link_operations.append(
                (source, staged_source, run_directory / staged_filename)
            )

    pending_copies = []
    for source, destination in copy_operations:
        if not os.path.lexists(destination):
            pending_copies.append((source, destination, False))
        elif destination.is_symlink() and destination.resolve() == source:
            pending_copies.append((source, destination, True))
        else:
            conflicts.append(str(destination))

    pending_links = []
    for source, staged_source, destination in link_operations:
        if not os.path.lexists(destination):
            pending_links.append((staged_source, destination, False))
        elif destination.is_symlink() and destination.resolve() == staged_source:
            continue
        elif copy and destination.is_symlink() and destination.resolve() == source:
            pending_links.append((staged_source, destination, True))
        else:
            conflicts.append(str(destination))
    if conflicts:
        raise FileExistsError("Refusing to overwrite: " + ", ".join(conflicts))

    created = []
    replaced_links = []
    try:
        for source, destination, replace_link in pending_copies:
            if replace_link:
                replaced_links.append((destination, os.readlink(destination)))
                destination.unlink()
            created.append(destination)
            shutil.copy2(source, destination)
            logger.debug("Copied %s to %s", source, destination)
        for source, destination, replace_link in pending_links:
            if replace_link:
                replaced_links.append((destination, os.readlink(destination)))
                destination.unlink()
            created.append(destination)
            destination.symlink_to(os.path.relpath(source, run_directory))
            logger.debug("Linked %s to %s", destination, source)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for path, target in reversed(replaced_links):
            if not os.path.lexists(path):
                path.symlink_to(target)
        raise

    return len(phantoms)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
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
            "Copy the named phantom tables into the run directory, then link "
            "the numbered AtRIS filenames to those local copies."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
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
        method = (
            "local copies and relative symbolic links"
            if args.copy
            else "relative symbolic links"
        )
        logger.info("Staged %i phantoms using %s", count, method)


if __name__ == "__main__":
    main()
