import sys

import numpy as np
import pytest

from atris_tools import nrlmsis2psf


def nrlmsis_row(altitude, latitude=10.0):
    row = np.ones(27)
    row[:5] = [2012, 5, 27, 148, 12]
    row[5:8] = [altitude, latitude, 10]
    return row


def write_table(path, rows):
    path.write_text("CCMC output\nYear Mon Day remaining columns\n")
    with path.open("a") as table:
        np.savetxt(table, rows)


def test_convert_merges_files_and_replaces_suspicious_duplicate(
    tmp_path, monkeypatch, capsys
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    bad_boundary = nrlmsis_row(2)
    bad_boundary[11] = 0
    write_table(first, [nrlmsis_row(0), nrlmsis_row(1), bad_boundary])
    write_table(second, [nrlmsis_row(2), nrlmsis_row(3)])
    monkeypatch.chdir(tmp_path)

    output = nrlmsis2psf.convert_nrlmsis([second, first])

    assert output == tmp_path / "simulation.psf"
    psf = np.loadtxt(output)
    assert psf.shape == (7, 16)
    np.testing.assert_allclose(psf[2:-1, 0], [6371, 6372, 6373, 6374])
    error = capsys.readouterr().err
    assert "Discarding suspicious NRLMSIS row at 2.000 km" in error


def test_merge_rejects_suspicious_row_without_valid_replacement(tmp_path):
    table = tmp_path / "bad.txt"
    bad_boundary = nrlmsis_row(2)
    bad_boundary[12] = 0
    write_table(table, [nrlmsis_row(0), nrlmsis_row(1), bad_boundary])

    with pytest.raises(ValueError, match="2.000 km have no valid replacement"):
        nrlmsis2psf.merge_nrlmsis([table])


def test_merge_replaces_malformed_boundary_row(tmp_path, capsys):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    write_table(first, [nrlmsis_row(0), nrlmsis_row(1)])
    fields = ["1"] * 27
    fields[5] = "2"
    fields[18] = "*******"
    with first.open("a") as table:
        table.write(" ".join(fields) + "\n")
    write_table(second, [nrlmsis_row(2), nrlmsis_row(3)])

    merged = nrlmsis2psf.merge_nrlmsis([first, second])

    np.testing.assert_allclose(merged[:, 5], [0, 1, 2, 3])
    assert "Discarding malformed NRLMSIS row at 2.000 km" in capsys.readouterr().err


def test_merge_rejects_missing_altitude_level(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    write_table(first, [nrlmsis_row(0), nrlmsis_row(1)])
    write_table(second, [nrlmsis_row(3), nrlmsis_row(4)])

    with pytest.raises(ValueError, match="complete, uniformly spaced grid"):
        nrlmsis2psf.merge_nrlmsis([first, second])


def test_merge_rejects_conflicting_valid_duplicate(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    original = nrlmsis_row(1)
    conflicting = nrlmsis_row(1)
    conflicting[11] = 2
    write_table(first, [nrlmsis_row(0), original])
    write_table(second, [conflicting, nrlmsis_row(2)])

    with pytest.raises(ValueError, match="Conflicting valid NRLMSIS rows"):
        nrlmsis2psf.merge_nrlmsis([first, second])


def test_merge_rejects_mismatched_request_parameters(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    write_table(first, [nrlmsis_row(0), nrlmsis_row(1)])
    write_table(
        second,
        [nrlmsis_row(2, latitude=20), nrlmsis_row(3, latitude=20)],
    )

    with pytest.raises(ValueError, match="common date, time, latitude"):
        nrlmsis2psf.merge_nrlmsis([first, second])


def test_main_accepts_multiple_input_files(monkeypatch, tmp_path):
    inputs = [tmp_path / "first.txt", tmp_path / "second.txt"]
    received = []
    monkeypatch.setattr(nrlmsis2psf, "convert_nrlmsis", received.extend)
    monkeypatch.setattr(
        sys,
        "argv",
        ["nrlmsis2psf", *(str(path) for path in inputs)],
    )

    nrlmsis2psf.main()

    assert received == inputs
