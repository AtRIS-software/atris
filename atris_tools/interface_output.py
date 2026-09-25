"""Read particle-interface records written by AtRIS output modes 0 and 1."""

from pathlib import Path

import numpy as np

from .binary_output import INTERFACE_RECORDS, read_records
from .root_output import has_ntuple, read_ntuple


FIELD_NAMES = (
    "pdg",
    "interface",
    "angle",
    "kinetic_energy",
    "source_energy",
)
BINARY_DTYPE = np.dtype(
    [
        ("pdg", np.int32),
        ("interface", np.uint16),
        ("angle", np.uint16),
        ("kinetic_energy", np.float32),
        ("source_energy", np.float32),
    ]
)
ROOT_FIELDS = (
    "pdg",
    "interface_id",
    "angle_degrees",
    "kinetic_energy_MeV",
    "primary_energy_MeV",
)


def read_binary(filename):
    """Read one native AtRIS mode-0 binary file."""
    return read_records(
        filename,
        INTERFACE_RECORDS,
        BINARY_DTYPE,
        allow_legacy=True,
    )


def read_ascii(filename):
    """Read one five-column file produced by atris-bin-to-ascii."""
    path = Path(filename)
    values = np.loadtxt(path, ndmin=2)
    if values.shape[1] != len(FIELD_NAMES):
        raise ValueError("%s must contain five columns" % path)
    if not np.all(values[:, :3] == np.trunc(values[:, :3])):
        raise ValueError("%s has non-integer PDG, interface, or angle values" % path)

    records = np.empty(values.shape[0], dtype=BINARY_DTYPE)
    for index, name in enumerate(FIELD_NAMES):
        records[name] = values[:, index]
    return records


def read_root(filename):
    """Read interface records from one AtRIS mode-1 ROOT file."""
    root_records = read_ntuple(filename, "interfaces", ROOT_FIELDS)
    records = np.empty(root_records.size, dtype=BINARY_DTYPE)
    for target, source in zip(FIELD_NAMES, ROOT_FIELDS):
        records[target] = root_records[source]
    return records


def read_interface_output(prefix):
    """Read available ROOT, binary, or historical ASCII interface output."""
    root_path = Path(str(prefix) + ".root")
    if root_path.is_file() and has_ntuple(root_path, "interfaces"):
        return read_root(root_path), root_path

    binary_path = Path(str(prefix) + ".binary")
    if binary_path.is_file():
        return read_binary(binary_path), binary_path

    ascii_path = Path(str(prefix) + ".ascii")
    if ascii_path.is_file():
        return read_ascii(ascii_path), ascii_path

    raise FileNotFoundError(
        "No interface output found in %s, %s, or %s"
        % (root_path, binary_path, ascii_path)
    )


def records_to_columns(records):
    """Return interface records as the historical five-column array."""
    return np.column_stack([records[name] for name in FIELD_NAMES])
