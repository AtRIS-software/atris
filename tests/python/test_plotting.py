import sys

import numpy as np

from atris_tools import plotting


def write_histogram(path, axes, row_count, column_count):
    header = [
        "#class tools::histo",
        "#title test",
        "#dimension " + str(len(axes)),
    ]
    header.extend(axes)
    while len(header) < (6 if len(axes) == 1 else 9):
        header.append("#metadata test")
    columns = "entries,Sw,Sw2,Sxw0,Sx2w0"
    if len(axes) == 2:
        columns += ",Sxw1,Sx2w1"
    path.write_text("\n".join(header + [columns]) + "\n")
    with path.open("a") as histogram:
        np.savetxt(
            histogram,
            np.ones((row_count, column_count)),
            delimiter=",",
        )


def prepare_processed_run(run_directory, phantom_count):
    (run_directory / "protons.mac").write_text(
        "/gps/hist/point 1 0\n"
        "/gps/hist/point 2 1\n"
        "/gps/hist/point 3 1\n"
    )
    write_histogram(
        run_directory / "protons_h1_h1.1.csv",
        ["#axis edges 1 2 3"],
        4,
        5,
    )
    for suffix in ("dir", "pos"):
        write_histogram(
            run_directory / ("protons_h2_h2." + suffix + ".csv"),
            ["#axis fixed 2 0 6.28319", "#axis fixed 2 0 1"],
            16,
            7,
        )

    response = np.array(
        [
            [0, 0.0, 1.0, 2.0],
            [1, 1.0, 3.0, 4.0],
            [2, 2.0, 5.0, 6.0],
        ]
    )
    np.savetxt(run_directory / "protons.ioni", response)

    phantom_rows = []
    for phantom_id in range(phantom_count):
        stem = "phantom_" + str(phantom_id)
        phantom_rows.append(
            "%i  %s  1.0  2.0\n" % (phantom_id, stem)
        )
        (run_directory / ("protons_h2_h2.dos%i.csv" % phantom_id)).touch()
        for extension in ("dose", "equi", "rates"):
            np.savetxt(
                run_directory / ("protons.%s%i" % (extension, phantom_id)),
                response,
            )
    if phantom_rows:
        (run_directory / "phantoms.txt").write_text("".join(phantom_rows))


def test_plot_run_writes_generic_and_per_phantom_pngs(tmp_path, monkeypatch):
    prepare_processed_run(tmp_path, 2)
    monkeypatch.chdir(tmp_path)

    plotting.plot_run("protons")

    assert sorted(path.name for path in tmp_path.glob("*.png")) == [
        "protons.phantom_0.png",
        "protons.phantom_1.png",
        "protons.png",
    ]
    for filename in tmp_path.glob("*.png"):
        assert filename.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_plot_run_without_phantoms_writes_only_generic_plot(
    tmp_path, monkeypatch
):
    prepare_processed_run(tmp_path, 0)
    monkeypatch.chdir(tmp_path)

    plotting.plot_run("protons")

    assert [path.name for path in tmp_path.glob("*.png")] == ["protons.png"]


def test_plot_convergence_writes_png_from_one_comparison(tmp_path, monkeypatch):
    (tmp_path / "protons.convergence.csv").write_text(
        "completed_chunks,primary_events,comparison_chunks,"
        "comparison_percent,ionization_change_percent,"
        "cell_change_p50_percent,cell_change_p90_percent,"
        "cell_relative_se_p50_percent,cell_relative_se_p90_percent\n"
        "2,600,1,50,12.5,8,25,15,40\n"
    )
    (tmp_path / "chunks.txt").write_text(
        "protons 111111 222222\n" * 20
    )
    monkeypatch.chdir(tmp_path)

    filename = plotting.plot_convergence("protons")

    assert filename == "protons.convergence.png"
    assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_convergence_ymax_ignores_highest_ten_percent():
    ordinary = np.arange(10, dtype=float)
    extreme = np.array([1000.0])

    ymax = plotting._convergence_ymax((ordinary, extreme))

    assert ymax < 1000.0
    assert ymax > ordinary[-1]


def test_log_125_ticks_labels_each_decade():
    major, minor = plotting._log_125_ticks((0.2, 60.0))

    np.testing.assert_allclose(major, [0.2, 0.5, 1, 2, 5, 10, 20, 50])
    assert 3 in minor
    assert 30 in minor


def test_inverse_sqrt_reference_recovers_expected_curve():
    chunks = np.array([4.0, 9.0, 16.0])
    expected = 20.0 / np.sqrt(chunks)

    np.testing.assert_allclose(
        plotting._inverse_sqrt_reference(chunks, expected), expected
    )


def test_asymptotic_uncertainty_fit_recovers_transient_curve():
    chunks = np.arange(2.0, 80.0)
    expected = 120.0 / np.sqrt(chunks) * (
        1.0 - 0.65 * np.exp(-chunks / 15.0)
    )

    fitted = plotting._asymptotic_uncertainty_fit(chunks, expected)

    np.testing.assert_allclose(fitted, expected, rtol=0.002)


def test_plot_run_uses_numbered_name_without_phantom_metadata(
    tmp_path, monkeypatch
):
    prepare_processed_run(tmp_path, 1)
    (tmp_path / "phantoms.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = plotting.plot_run("protons")

    assert sorted(filenames) == ["protons.phantom-0.png", "protons.png"]
    assert errors == []


def test_plot_run_reports_missing_quantity_and_plots_the_rest(
    tmp_path, monkeypatch
):
    prepare_processed_run(tmp_path, 1)
    (tmp_path / "protons.equi0").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = plotting.plot_run("protons")

    assert sorted(filenames) == ["protons.phantom_0.png", "protons.png"]
    assert errors == ["protons results: missing protons.equi0"]


def test_plot_run_warns_when_current_bins_do_not_match_output(
    tmp_path, monkeypatch, capsys
):
    prepare_processed_run(tmp_path, 0)
    np.savetxt(tmp_path / "protons.bins", [1, 2, 4])
    monkeypatch.chdir(tmp_path)

    filenames, errors = plotting.plot_run("protons")

    assert filenames == ["protons.png"]
    assert errors == []
    assert (
        "WARNING: protons: protons.bins does not match the energy edges "
        "recorded in protons_h1_h1.1.csv"
        in capsys.readouterr().err
    )


def test_main_skips_species_without_processed_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["atris-plot", str(tmp_path)])

    plotting.main()

    output = capsys.readouterr().out
    assert "Skipping protons response plots: processed output not found." in output
    assert "Skipping alphas response plots: processed output not found." in output
