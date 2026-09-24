import argparse
from pathlib import Path

import numpy as np

from .binary_output import INTERFACE_RECORDS
from .cli import HelpFormatter, add_version_argument
from .dump import read_binary_output
from .interface_output import records_to_columns


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Convert native AtRIS mode-0 particle-interface records from "
            "binary to the historical five-column ASCII format."
        ),
        epilog=(
            "The output defaults to the input basename with an .ascii suffix, "
            "replacing an existing file. The binary input is retained. This "
            "command does not gather chunks, post-process response histograms, "
            "or make plots; the binary representation remains faster and "
            "smaller for normal analysis."
        ),
    )
    parser.add_argument(
        "binary_file",
        type=Path,
        metavar="BINARY_FILE",
        help="AtRIS mode-0 binary file to convert.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="ASCII_FILE",
        help="ASCII file to write (default: input basename with .ascii suffix).",
    )
    add_version_argument(parser)
    args = parser.parse_args()

    input_path = args.binary_file
    output_path = args.output or input_path.with_suffix(".ascii")
    print("### AtRIS: reading binary data....", end="")
    record_type, records, _ = read_binary_output(input_path)
    if record_type != INTERFACE_RECORDS:
        raise ValueError(str(input_path) + " does not contain interface records")
    d = records_to_columns(records)
    print(".........done.")
    print("### AtRIS: now saving the data....", end="")
    fmt = "%i %i %i %f %f"
    np.savetxt(output_path, d, fmt=fmt)
    print(".........done. Thank you for using this script")
    print("additional debuging")
    print("col 1:", np.min(d[:,0]), np.max(d[:,0]))
    print("col 1:", np.min(d[:,1]), np.max(d[:,1]))
    print("col 1:", np.min(d[:,2]), np.max(d[:,2]), "downward ", np.sum(d[:,2]>90), " upward", np.sum(d[:,2]<90))
    print("col 1:", np.min(d[:,3]), np.max(d[:,3]))
    print("col 1:", np.min(d[:,4]), np.max(d[:,4]))


if __name__ == "__main__":
    main()
