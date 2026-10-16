import logging

import numpy as np
import uproot

from atris_tools import plotting
from atris_tools.root_records import INTERFACE_DTYPE


def test_plot_interface_output_reads_root_and_ignores_invalid_energy(
    tmp_path, monkeypatch, caplog, gdml_text
):
    records = np.array(
        [
            (2212, 1, 120, 100.0, 100.0),
            (2212, 2, 60, 80.0, 100.0),
            (22, 2, 95, 10.0, 100.0),
            (11, 3, 45, 1.0, 10.0),
            (2212, 4, 0, 0.0, 100.0),
        ],
        dtype=INTERFACE_DTYPE,
    )
    path = tmp_path / "protons.root"
    with uproot.recreate(path) as root_file:
        root_file.mktree(
            "interfaces",
            {
                "pdg": "int32",
                "interface_id": "int32",
                "angle_degrees": "int32",
                "kinetic_energy_MeV": "float64",
                "primary_energy_MeV": "float64",
            },
        )
        root_file["interfaces"].extend(
            {
                "pdg": records["pdg"],
                "interface_id": records["interface"],
                "angle_degrees": records["angle"],
                "kinetic_energy_MeV": records["kinetic_energy"],
                "primary_energy_MeV": records["source_energy"],
            }
        )
    (tmp_path / "protons.gdml").write_text(gdml_text)
    monkeypatch.chdir(tmp_path)

    with caplog.at_level(logging.WARNING, logger="atris_tools.interface_plotting"):
        filename = plotting.plot_interface_output("protons")

    assert filename == "protons.interfaces.png"
    assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (
        "protons.root: ignoring 1 non-positive or non-finite energy records"
        in caplog.messages
    )
