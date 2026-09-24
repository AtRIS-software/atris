"""Dump an AtRIS binary output file as CSV text."""

import argparse
import csv
import os
from pathlib import Path
import sys

from .binary_output import INTERFACE_RECORDS, STEP_RECORDS, read_header
from .cli import HelpFormatter, add_version_argument
from .interface_output import BINARY_DTYPE, read_binary
from .step_output import STEP_DTYPE, process_name, read_step_records


def _field_value(record, name):
    kind = record.dtype.fields[name][0].kind
    value = record[name]
    if kind in "iu":
        return int(value)
    if kind == "f":
        return float(value)
    if kind == "S":
        return process_name(value)
    return value


def read_binary_output(path):
    """Read an AtRIS binary file and identify its record type and fields."""
    header = read_header(path)
    record_type = header["record_type"] if header else INTERFACE_RECORDS
    if record_type == INTERFACE_RECORDS:
        records = read_binary(path)
        names = BINARY_DTYPE.names
    elif record_type == STEP_RECORDS:
        records = read_step_records(path)
        names = STEP_DTYPE.names
    else:
        raise ValueError(str(path) + " contains an unknown AtRIS record type")
    return record_type, records, names


def dump_binary(path, stream):
    """Write one AtRIS binary file as CSV to a text stream."""
    _, records, names = read_binary_output(path)

    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(names)
    for record in records:
        writer.writerow([_field_value(record, name) for name in names])


def main():
    """Run the AtRIS binary-output dumper."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Dump an AtRIS interface or transport-step binary output file "
            "as CSV text on standard output."
        ),
        epilog=(
            "The input file is not modified. Pipe the output to tools such as "
            "head or redirect it to a text file. Headerless mode-0 interface "
            "files produced by earlier AtRIS versions are also supported."
        ),
    )
    parser.add_argument(
        "binary_file",
        type=Path,
        metavar="BINARY_FILE",
        help="AtRIS .binary or .steps.binary file to dump.",
    )
    add_version_argument(parser)
    args = parser.parse_args()
    try:
        dump_binary(args.binary_file, sys.stdout)
        sys.stdout.flush()
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w")
    return 0


if __name__ == "__main__":
    main()
