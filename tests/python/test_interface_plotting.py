import numpy as np
import pytest

from atris_tools import plotting
from atris_tools.interface_output import BINARY_DTYPE, records_to_columns


@pytest.mark.parametrize("extension", ["binary", "asci"])
def test_plot_interface_output_reads_binary_or_ascii(
    tmp_path, monkeypatch, extension
):
    records = np.array(
        [
            (2212, 1, 120, 100.0, 100.0),
            (2212, 2, 60, 80.0, 100.0),
            (22, 2, 95, 10.0, 100.0),
            (11, 3, 45, 1.0, 10.0),
        ],
        dtype=BINARY_DTYPE,
    )
    path = tmp_path / ("protons." + extension)
    if extension == "binary":
        records.tofile(path)
    else:
        np.savetxt(path, records_to_columns(records))
    monkeypatch.chdir(tmp_path)

    filename = plotting.plot_interface_output("protons")

    assert filename == "protons.interfaces.png"
    assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
