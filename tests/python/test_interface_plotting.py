import logging

import numpy as np
import pytest

from atris_tools import plotting
from atris_tools.binary_output import INTERFACE_RECORDS, write_header
from atris_tools.interface_output import BINARY_DTYPE, records_to_columns


@pytest.mark.parametrize("extension", ["binary", "ascii"])
def test_plot_interface_output_reads_binary_or_ascii_and_ignores_invalid_energy(
    tmp_path, monkeypatch, caplog, extension, gdml_text
):
    records = np.array(
        [
            (2212, 1, 120, 100.0, 100.0),
            (2212, 2, 60, 80.0, 100.0),
            (22, 2, 95, 10.0, 100.0),
            (11, 3, 45, 1.0, 10.0),
            (2212, 4, 0, 0.0, 100.0),
        ],
        dtype=BINARY_DTYPE,
    )
    path = tmp_path / ("protons." + extension)
    if extension == "binary":
        with path.open("wb") as stream:
            write_header(stream, INTERFACE_RECORDS, BINARY_DTYPE.itemsize)
            records.tofile(stream)
    else:
        np.savetxt(path, records_to_columns(records))
    (tmp_path / "protons.gdml").write_text(gdml_text)
    monkeypatch.chdir(tmp_path)

    with caplog.at_level(logging.WARNING, logger="atris_tools.interface_plotting"):
        filename = plotting.plot_interface_output("protons")

    assert filename == "protons.interfaces.png"
    assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (
        "protons.%s: ignoring 1 non-positive or non-finite energy records"
        % extension
    ) in caplog.messages
