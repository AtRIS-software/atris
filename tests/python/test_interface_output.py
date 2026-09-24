import sys

import numpy as np
import pytest

from atris_tools import bin2asci
from atris_tools.interface_output import (
    BINARY_DTYPE,
    read_ascii,
    read_binary,
    read_interface_output,
    records_to_columns,
)


SAMPLE_RECORDS = np.array(
    [
        (2212, 2, 125, 100.0, 100.0),
        (22, 3, 45, 12.5, 100.0),
        (11, 4, 92, 1.25, 10.0),
    ],
    dtype=BINARY_DTYPE,
)


def test_read_binary_and_ascii_return_the_same_records(tmp_path):
    binary_path = tmp_path / "protons.binary"
    ascii_path = tmp_path / "protons.asci"
    SAMPLE_RECORDS.tofile(binary_path)
    np.savetxt(ascii_path, records_to_columns(SAMPLE_RECORDS))

    np.testing.assert_array_equal(read_binary(binary_path), SAMPLE_RECORDS)
    np.testing.assert_array_equal(read_ascii(ascii_path), SAMPLE_RECORDS)


def test_read_interface_output_prefers_binary(tmp_path):
    SAMPLE_RECORDS.tofile(tmp_path / "protons.binary")
    np.savetxt(
        tmp_path / "protons.asci",
        records_to_columns(SAMPLE_RECORDS[:1]),
    )

    records, source = read_interface_output(tmp_path / "protons")

    np.testing.assert_array_equal(records, SAMPLE_RECORDS)
    assert source.name == "protons.binary"


def test_read_binary_rejects_incomplete_record(tmp_path):
    path = tmp_path / "protons.binary"
    path.write_bytes(b"incomplete")

    with pytest.raises(ValueError, match="complete 16-byte records"):
        read_binary(path)


def test_binary_to_ascii_uses_shared_reader(tmp_path, monkeypatch):
    SAMPLE_RECORDS.tofile(tmp_path / "protons.binary")
    monkeypatch.setattr(
        sys,
        "argv",
        ["atris-bin-to-ascii", str(tmp_path / "protons.binary")],
    )

    bin2asci.main()

    np.testing.assert_array_equal(
        read_ascii(tmp_path / "protons.asci"), SAMPLE_RECORDS
    )


def test_binary_to_ascii_accepts_output_path(tmp_path, monkeypatch):
    input_path = tmp_path / "protons.binary"
    output_path = tmp_path / "particles.txt"
    SAMPLE_RECORDS.tofile(input_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "atris-bin-to-ascii",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    bin2asci.main()

    np.testing.assert_array_equal(read_ascii(output_path), SAMPLE_RECORDS)
