import sys

import numpy as np
import pytest

from atris_tools import plotting, step_plotting
from atris_tools.binary_output import STEP_RECORDS, write_header
from atris_tools.step_output import STEP_DTYPE


TRACE_ROWS = (
    (
        0, 1, 0, 1, 2212, 2,
        0, 0, 2, 0, 0, 1,
        100, 90, 10, 0, 1, 2, 100,
        "primary", "Transportation",
    ),
    (
        0, 2, 1, 1, 11, 1,
        0, 0, 1, 0, 0, 0,
        5, 4, 1, 0, 1, 3, 100,
        "protonInelastic", "eIoni",
    ),
    (
        1, 1, 0, 1, 2212, 2,
        0, 0, 2, 0, 0, 1,
        50, 45, 5, 0, 1, 2, 50,
        "primary", "Transportation",
    ),
)


def write_step_trace(path, rows=TRACE_ROWS):
    records = np.zeros(len(rows), dtype=STEP_DTYPE)
    for record, values in zip(records, rows):
        for name, value in zip(STEP_DTYPE.names, values):
            record[name] = value
    with path.open("wb") as stream:
        write_header(stream, STEP_RECORDS, STEP_DTYPE.itemsize)
        records.tofile(stream)


def test_step_reader_rejects_partial_binary_record(tmp_path):
    path = tmp_path / "protons.steps.binary"
    with path.open("wb") as stream:
        write_header(stream, STEP_RECORDS, STEP_DTYPE.itemsize)
        stream.write(b"incomplete")

    with pytest.raises(ValueError, match="complete 256-byte records"):
        step_plotting.read_step_trace(path)


def test_read_step_trace_streams_aggregates_and_bounded_sample(tmp_path):
    path = tmp_path / "protons.steps.binary"
    write_step_trace(path)

    summary = step_plotting.read_step_trace(path, sample_limit=2)

    assert summary["row_count"] == 3
    assert (summary["first_event"], summary["last_event"]) == (0, 1)
    assert summary["event_counts"] == {0: 2, 1: 1}
    assert summary["particle_counts"] == {2212: 2, 11: 1}
    assert summary["process_counts"] == {"Transportation": 2, "eIoni": 1}
    assert summary["detector_counts"] == {2: 2, 1: 1}
    assert summary["detector_deposit"] == {2: 15.0, 1: 1.0}
    assert len(summary["energy_sample"]) == 2
    assert summary["positive_energy_rows"] == 3


def test_plot_mode_one_output_writes_overview_and_shower_pngs(
    tmp_path, monkeypatch, gdml_text
):
    write_step_trace(tmp_path / "protons.steps.binary")
    (tmp_path / "protons.gdml").write_text(gdml_text)
    monkeypatch.chdir(tmp_path)

    filenames = step_plotting.plot_mode_one_output("protons")

    assert filenames == ["protons.steps.png", "protons.shower.png"]
    for filename in filenames:
        assert (tmp_path / filename).read_bytes().startswith(
            b"\x89PNG\r\n\x1a\n"
        )


def test_atris_plot_routes_mode_one_outputs_to_both_plotters(
    tmp_path, monkeypatch
):
    write_step_trace(tmp_path / "protons.steps.binary")
    (tmp_path / "protons.binary").write_bytes(b"")
    step_calls = []
    interface_calls = []
    monkeypatch.setattr(sys, "argv", ["atris-plot", str(tmp_path)])
    monkeypatch.setattr(plotting, "plot_inputs", lambda: ([], []))
    monkeypatch.setattr(
        plotting,
        "plot_mode_one_output",
        lambda simulation: step_calls.append(simulation)
        or [simulation + ".steps.png", simulation + ".shower.png"],
    )
    monkeypatch.setattr(
        plotting,
        "plot_interface_output",
        lambda simulation: interface_calls.append(simulation)
        or simulation + ".interfaces.png",
    )

    plotting.main()

    assert interface_calls == ["protons"]
    assert step_calls == ["protons"]
