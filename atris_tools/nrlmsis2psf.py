#!/usr/bin/env python3
"""Convert a downloaded NASA NRLMSIS table to AtRIS PSF."""

import argparse
import logging
from pathlib import Path

import numpy as np

from . import nrlmsis
from .cli import add_logging_arguments, configure_logging


HEADER_MARKER = "Year Mon Day"
METADATA_COLUMNS = (0, 1, 2, 3, 4, 6, 7)
DUPLICATE_RELATIVE_TOLERANCE = 5.0e-4
logger = logging.getLogger(__name__)


def _read_table(path):
    path = Path(path)
    table = path.read_text(encoding="utf-8")
    lines = table.splitlines()
    header_indices = [
        index for index, line in enumerate(lines) if HEADER_MARKER in line
    ]
    if not header_indices:
        raise ValueError("NRLMSIS table header not found in " + str(path))

    parsed = []
    malformed = []
    for line_number, line in enumerate(
        lines[header_indices[0] + 1 :],
        start=header_indices[0] + 2,
    ):
        fields = line.split()
        if not fields:
            continue
        altitude = None
        if len(fields) > 5:
            try:
                altitude = _altitude_key(fields[5])
            except ValueError:
                pass
        try:
            values = [float(field) for field in fields]
        except ValueError:
            if altitude is None:
                raise ValueError(
                    "Could not identify malformed NRLMSIS row in %s:%i"
                    % (path, line_number)
                )
            malformed.append(altitude)
            continue
        parsed.append((line_number, altitude, values))

    if not parsed:
        raise ValueError("No valid NRLMSIS rows found in " + str(path))
    column_counts = [len(values) for _, _, values in parsed]
    expected_columns = max(set(column_counts), key=column_counts.count)
    rows = []
    for line_number, altitude, values in parsed:
        if len(values) != expected_columns:
            if altitude is None:
                raise ValueError(
                    "Could not identify malformed NRLMSIS row in %s:%i"
                    % (path, line_number)
                )
            malformed.append(altitude)
            continue
        rows.append(values)
    return path, np.asarray(rows), malformed


def _altitude_key(altitude):
    return round(float(altitude), 9)


def _suspicious_rows(atmosphere):
    physical = nrlmsis.nrlm_reformer(atmosphere)
    return ~np.all(np.isfinite(physical), axis=1) | np.any(
        physical[:, 1:] <= 0,
        axis=1,
    )


def merge_nrlmsis(input_paths):
    """Merge compatible NRLMSIS tables into one validated altitude profile."""
    tables = [_read_table(path) for path in input_paths]
    if not tables:
        raise ValueError("At least one NRLMSIS table is required")

    column_count = tables[0][1].shape[1]
    if column_count < 18:
        raise ValueError(
            "%s has only %i columns; expected an NRLMSIS profile table"
            % (tables[0][0], column_count)
        )
    valid_rows = {}
    rejected_rows = {}
    for path, atmosphere, malformed_altitudes in tables:
        if atmosphere.shape[1] != column_count:
            raise ValueError(
                "%s has %i columns; expected %i"
                % (path, atmosphere.shape[1], column_count)
            )
        for altitude in malformed_altitudes:
            rejected_rows.setdefault(altitude, []).append(path)
            logger.warning(
                "Discarding malformed NRLMSIS row at %.3f km from %s",
                altitude,
                path,
            )
        suspicious = _suspicious_rows(atmosphere)
        for row, reject in zip(atmosphere, suspicious):
            altitude = _altitude_key(row[5])
            if reject:
                rejected_rows.setdefault(altitude, []).append(path)
                logger.warning(
                    "Discarding suspicious NRLMSIS row at %.3f km from %s",
                    altitude,
                    path,
                )
                continue
            if altitude in valid_rows:
                previous_path, previous_row = valid_rows[altitude]
                # CCMC prints about four significant digits, so repeated
                # boundary rows can differ in their final printed digit.
                if not np.allclose(
                    previous_row,
                    row,
                    rtol=DUPLICATE_RELATIVE_TOLERANCE,
                    atol=0.0,
                ):
                    raise ValueError(
                        "Conflicting valid NRLMSIS rows at %.3f km in %s and %s"
                        % (altitude, previous_path, path)
                    )
                continue
            valid_rows[altitude] = (path, row)

    missing_replacements = sorted(set(rejected_rows) - set(valid_rows))
    if missing_replacements:
        altitudes = ", ".join("%.3f" % value for value in missing_replacements)
        raise ValueError(
            "Suspicious NRLMSIS rows at %s km have no valid replacement"
            % altitudes
        )

    altitudes = sorted(valid_rows)
    if len(altitudes) < 2:
        raise ValueError("The merged NRLMSIS profile requires at least two rows")
    merged = np.vstack([valid_rows[altitude][1] for altitude in altitudes])

    reference_metadata = merged[0, METADATA_COLUMNS]
    if not np.allclose(
        merged[:, METADATA_COLUMNS],
        reference_metadata,
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise ValueError(
            "NRLMSIS tables do not use one common date, time, latitude, and longitude"
        )

    differences = np.diff(merged[:, 5])
    step = np.min(differences)
    tolerance = max(1.0e-9, step * 1.0e-6)
    if step <= 0 or not np.allclose(
        differences,
        step,
        rtol=0.0,
        atol=tolerance,
    ):
        raise ValueError(
            "Merged NRLMSIS altitudes are not a complete, uniformly spaced grid"
        )

    logger.info(
        "Merged %i NRLMSIS file(s) into %i rows from %.3f to %.3f km "
        "with a %.3f km step.",
        len(tables),
        len(merged),
        merged[0, 5],
        merged[-1, 5],
        step,
    )
    return merged


def _validate_psf(path, atmosphere_rows):
    output = np.atleast_2d(np.loadtxt(path))
    expected_rows = atmosphere_rows + 3
    if output.shape != (expected_rows, 16):
        raise RuntimeError(
            "simulation.psf has shape %s; expected (%i, 16)"
            % (output.shape, expected_rows)
        )
    atmosphere = output[2:-1]
    physical = atmosphere[:, [7, 8, 9, 11, 12, 13, 14, 15]]
    if not np.all(np.isfinite(physical)) or np.any(physical <= 0):
        raise RuntimeError(
            "simulation.psf contains non-finite, zero, or negative atmospheric values"
        )


def convert_nrlmsis(input_paths):
    """Convert one or more downloaded NRLMSIS tables to an AtRIS PSF."""
    if isinstance(input_paths, (str, Path)):
        input_paths = [input_paths]
    atmosphere = merge_nrlmsis(input_paths)
    nrlmsis.nrml2psf(nrlmsis.nrlm_reformer(atmosphere))
    output_path = Path.cwd() / "simulation.psf"
    _validate_psf(output_path, len(atmosphere))
    logger.info("Wrote %s", output_path)
    return output_path


def main():
    """Run the NRLMSIS-to-PSF command."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert one or more NASA CCMC NRLMSIS text tables into the "
            "Planet Specification Format (PSF) used by AtRIS."
        ),
        epilog=(
            "This command does not download atmosphere data. Input tables may "
            "overlap and may be supplied in any altitude order, but they must "
            "describe the same location and time and combine into a complete, "
            "uniformly spaced altitude grid. The result is written as "
            "simulation.psf in the current directory, replacing that file if "
            "it already exists."
        ),
    )
    parser.add_argument(
        "nrlmsis_output",
        nargs="+",
        type=Path,
        metavar="TABLE",
        help=(
            "Downloaded NRLMSIS text table. Supply multiple tables when the "
            "altitude profile was downloaded in chunks."
        ),
    )
    add_logging_arguments(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)
    convert_nrlmsis(args.nrlmsis_output)


if __name__ == "__main__":
    main()
