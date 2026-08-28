import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

from atris_tools import postprocess


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


def test_process_psf_and_phantoms_return_numpy_data(tmp_path, monkeypatch):
    geometry, detector_count = postprocess.process_psf(FIXTURE / "simulation.psf")

    assert detector_count == 2
    assert geometry.keys() == {"sdid", "volume/cm3", "inn_surface/cm2"}
    np.testing.assert_array_equal(geometry["sdid"], [0, 1])
    assert all(isinstance(values, np.ndarray) for values in geometry.values())

    shutil.copy2(FIXTURE / "phantoms.txt", tmp_path)
    monkeypatch.chdir(tmp_path)
    phantoms = postprocess.process_phantoms(1)
    np.testing.assert_allclose(phantoms, [[14094.7550, 1413.72]])


def test_process_phantoms_accepts_run_without_phantoms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms(0)

    assert phantoms.shape == (0, 2)


def test_process_phantoms_uses_ids_independently_of_row_order(tmp_path, monkeypatch):
    (tmp_path / "phantoms.txt").write_text(
        "1  second  30.5 40.5\n"
        "0  first   10.5 20.5\n"
    )
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms(2)

    np.testing.assert_allclose(phantoms, [[10.5, 20.5], [30.5, 40.5]])


def test_process_run_reports_missing_plot_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "atris_tools.plotting", None)

    with pytest.raises(RuntimeError, match="plot.*extra"):
        postprocess.process_run("protons")
