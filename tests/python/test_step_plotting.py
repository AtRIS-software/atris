import csv
import sys

import pytest

from atris_tools import plotting, step_plotting


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
    with path.open("w", newline="") as trace:
        trace.write(step_plotting.TRACE_MARKER + "\n")
        writer = csv.writer(trace)
        writer.writerow(step_plotting.TRACE_COLUMNS)
        writer.writerows(rows)


def test_step_trace_detection_distinguishes_mode_one_from_mode_zero(tmp_path):
    step_path = tmp_path / "protons.asci"
    interface_path = tmp_path / "alphas.asci"
    write_step_trace(step_path)
    interface_path.write_text("2212 1 90 100 100\n")

    assert step_plotting.is_step_trace(step_path)
    assert not step_plotting.is_step_trace(interface_path)


def test_read_step_trace_streams_aggregates_and_bounded_sample(tmp_path):
    path = tmp_path / "protons.asci"
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


def test_read_step_trace_rejects_unknown_header(tmp_path):
    path = tmp_path / "protons.asci"
    path.write_text(step_plotting.TRACE_MARKER + "\nevent_id,pdg\n0,2212\n")

    with pytest.raises(ValueError, match="unexpected step-trace header"):
        step_plotting.read_step_trace(path)


def test_plot_mode_one_output_writes_overview_and_shower_pngs(
    tmp_path, monkeypatch, gdml_text
):
    write_step_trace(tmp_path / "protons.asci")
    (tmp_path / "protons.gdml").write_text(gdml_text)
    monkeypatch.chdir(tmp_path)

    filenames = step_plotting.plot_mode_one_output("protons")

    assert filenames == ["protons.steps.png", "protons.shower.png"]
    for filename in filenames:
        assert (tmp_path / filename).read_bytes().startswith(
            b"\x89PNG\r\n\x1a\n"
        )


def test_atris_plot_routes_mode_one_trace_to_step_plotter(
    tmp_path, monkeypatch
):
    write_step_trace(tmp_path / "protons.asci")
    calls = []
    monkeypatch.setattr(sys, "argv", ["atris-plot", str(tmp_path)])
    monkeypatch.setattr(plotting, "plot_inputs", lambda: ([], []))
    monkeypatch.setattr(
        plotting,
        "plot_mode_one_output",
        lambda simulation: calls.append(simulation)
        or [simulation + ".steps.png", simulation + ".shower.png"],
    )
    monkeypatch.setattr(
        plotting,
        "plot_interface_output",
        lambda simulation: pytest.fail("mode-1 trace used the mode-0 plotter"),
    )

    plotting.main()

    assert calls == ["protons"]
