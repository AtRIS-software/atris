""""""

from io import StringIO
from pathlib import Path
import argparse
import logging
import os
import shutil

from .cli import HelpFormatter, add_logging_arguments, add_version_argument, configure_logging
from .phantom_table import RESPONSE_ENERGY_BINS


logger = logging.getLogger(__name__)


def read_phantom_selection(run_directory):
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


def _remove_staged_links(run_directory, phantom_id):
    for prefix in ("radiation_phantom", "counting_phantom"):
        path = run_directory / (prefix + str(phantom_id) + ".txt")
        if path.is_symlink():
            path.unlink()
            logger.debug("Removed symbolic link %s", path)


def _dummy_counting_contents(response_file):
    from .phantom_table import PhantomTable, COUNTING_EFFICIENCY

    with response_file.open() as stream:
        header = next(
            (
                line.split("#", 1)[0].strip()
                for line in stream
                if line.split("#", 1)[0].strip()
            ),
            "",
        )
    try:
        particle_codes = [int(value) for value in header.split()]
    except ValueError as error:
        raise ValueError("Invalid particle header in " + str(response_file)) from error
    if not particle_codes:
        raise ValueError("Empty particle header in " + str(response_file))

    table = PhantomTable(
        particle_codes,
        [[1.0] * RESPONSE_ENERGY_BINS] * len(particle_codes),
        COUNTING_EFFICIENCY,
        metadata={
            "counting_definition": "dummy values of one; not a calculated detection efficiency",
            "source_response_table": response_file.name,
        },
    )
    output = StringIO()
    table.write(output, fmt="%.6e")
    return output.getvalue()


def _stage_phantom(
    phantom,
    run_directory,
    archive,
    copy,
    accept_missing_counting,
):
    phantom_id = phantom["id"]
    stem = phantom["stem"]
    response_filename = stem + "_response.txt"
    response_source = find_phantom_file(response_filename, run_directory, archive)
    counting_filename = stem + "_counting.txt"
    dummy = None
    try:
        counting_source = find_phantom_file(counting_filename, run_directory, archive)
    except FileNotFoundError:
        if not accept_missing_counting:
            raise
        counting_filename = stem + "_dummy_counting.txt"
        counting_source = run_directory / counting_filename
        dummy = (counting_source, _dummy_counting_contents(response_source))

    copy_operations = []
    link_operations = []
    for filename, staged_filename, source, copy_source in (
        (
            response_filename,
            "radiation_phantom" + str(phantom_id) + ".txt",
            response_source,
            True,
        ),
        (
            counting_filename,
            "counting_phantom" + str(phantom_id) + ".txt",
            counting_source,
            dummy is None,
        ),
    ):
        staged_source = source
        if copy and copy_source:
            staged_source = run_directory / Path(filename).name
            if source != staged_source:
                copy_operations.append((source, staged_source))
        link_operations.append((staged_source, run_directory / staged_filename))

    conflicts = []
    pending_dummy = None
    if dummy is not None:
        destination, contents = dummy
        if not os.path.lexists(destination):
            pending_dummy = (destination, contents, False)
        elif destination.is_symlink():
            pending_dummy = (destination, contents, True)
        elif not destination.is_file() or destination.read_text() != contents:
            conflicts.append(str(destination))

    pending_copies = []
    for source, destination in copy_operations:
        if not os.path.lexists(destination):
            pending_copies.append((source, destination, False))
        elif destination.is_symlink():
            pending_copies.append((source, destination, True))
        else:
            conflicts.append(str(destination))

    pending_links = []
    for source, destination in link_operations:
        if not os.path.lexists(destination):
            pending_links.append((source, destination))
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
        if pending_dummy is not None:
            destination, contents, replace_link = pending_dummy
            if replace_link:
                replaced_links.append((destination, os.readlink(destination)))
                destination.unlink()
            created.append(destination)
            destination.write_text(contents)
            logger.debug("Created dummy counting response %s", destination)
        for source, destination in pending_links:
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

    if dummy is not None:
        logger.info(
            "Using dummy counting response with values of one for phantom %i "
            "(%s): %s",
            phantom_id,
            stem,
            counting_source,
        )


def stage_phantoms(
    run_directory,
    archive=None,
    copy=False,
    accept_missing_counting=False,
):
    run_directory = Path(run_directory).resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))
    if archive is not None:
        archive = Path(archive).resolve()

    phantoms = read_phantom_selection(run_directory)
    selected_ids = {phantom["id"] for phantom in phantoms}
    for prefix in ("radiation_phantom", "counting_phantom"):
        for path in run_directory.glob(prefix + "*.txt"):
            id_text = path.name[len(prefix) : -len(".txt")]
            if path.is_symlink() and id_text.isdigit():
                if int(id_text) not in selected_ids:
                    path.unlink()
                    logger.debug("Removed symbolic link %s", path)

    staged = 0
    for phantom in phantoms:
        _remove_staged_links(run_directory, phantom["id"])
        try:
            _stage_phantom(
                phantom,
                run_directory,
                archive,
                copy,
                accept_missing_counting,
            )
        except (OSError, ValueError) as error:
            logger.error(
                "Could not stage phantom %i (%s): %s",
                phantom["id"],
                phantom["stem"],
                error,
            )
            continue
        staged += 1
    return staged


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
            "radiation-response tables or change phantoms.txt. Symbolic links are "
            "updated to match the current selection, while regular destination "
            "files are not overwritten. An error in one row does not prevent "
            "other rows from being staged."
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
    parser.add_argument(
        "--accept-missing-counting",
        action="store_true",
        help=(
            "Accept a missing counting-response table by creating a local "
            "dummy table whose counting values are all one. A real counting "
            "table is always used when available."
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
        accept_missing_counting=args.accept_missing_counting,
    )
    if count == 0:
        logger.info("No phantoms staged")
    else:
        method = (
            "local copies and relative symbolic links"
            if args.copy
            else "relative symbolic links"
        )
        logger.info(
            "Staged %i phantom%s using %s",
            count,
            "" if count == 1 else "s",
            method,
        )


if __name__ == "__main__":
    main()
