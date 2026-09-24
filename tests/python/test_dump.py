from io import StringIO

import numpy as np

from atris_tools.binary_output import (
    INTERFACE_RECORDS,
    STEP_RECORDS,
    write_header,
)
from atris_tools.dump import dump_binary
from atris_tools.interface_output import BINARY_DTYPE
from atris_tools.step_output import STEP_DTYPE


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


def test_dumps_step_records_as_csv(tmp_path):
    path = tmp_path / "protons.steps.binary"
    records = np.zeros(1, dtype=STEP_DTYPE)
    records["event_id"] = 4
    records["track_id"] = 7
    records["pdg"] = 2212
    records["post_kinetic_energy_MeV"] = 25.0
    records["creator_process"] = "primary"
    records["step_process"] = "Transportation"
    write_records(path, STEP_RECORDS, records)
    output = StringIO()

    dump_binary(path, output)

    lines = output.getvalue().splitlines()
    assert lines[0].startswith("event_id,track_id,parent_id,step_id,pdg")
    assert lines[1].endswith(",primary,Transportation")
    assert lines[1].split(",")[:5] == ["4", "7", "0", "0", "2212"]
