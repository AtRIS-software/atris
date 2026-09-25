from io import StringIO

import numpy as np

from atris_tools.binary_output import (
    INTERFACE_RECORDS,
    write_header,
)
from atris_tools.dump import dump_binary
from atris_tools.interface_output import BINARY_DTYPE


def write_records(path, record_type, records):
    with path.open("wb") as stream:
        write_header(stream, record_type, records.dtype.itemsize)
        records.tofile(stream)


def test_dumps_interface_records_as_csv(tmp_path):
    path = tmp_path / "protons.binary"
    records = np.array([(2212, 2, 90, 10.0, 100.0)], dtype=BINARY_DTYPE)
    write_records(path, INTERFACE_RECORDS, records)
    output = StringIO()

    dump_binary(path, output)

    assert output.getvalue().splitlines() == [
        "pdg,interface,angle,kinetic_energy,source_energy",
        "2212,2,90,10.0,100.0",
    ]
