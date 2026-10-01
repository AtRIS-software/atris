"""Characterize the observable AtRIS command-line contract.

Tests whose names contain ``currently`` record permissive behavior in the
existing executable; they do not imply that the behavior is desirable.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
import pytest

from atris_tools.step_output import process_name, read_step_records


REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "minimal"
PHANTOMS = REPOSITORY_ROOT / "phantoms"
EXPECTED_HISTOGRAM_SUFFIXES = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.dos0.csv",
    "_h2_h2.equi0.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
    "_h2_h2.rates0.csv",
}
EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
}


@pytest.fixture(scope="session")
def atris_command():
    command = shutil.which("AtRIS")
    if command is None:
        pytest.fail(
            "AtRIS is not on PATH; source atris/setup_atris.sh from the "
            "workspace root before running tests/regression"
        )
    return command


def prepare_run(run_directory, *, chunked=False):
    shutil.copyfile(FIXTURE / "simulation.gdml", run_directory / "protons.gdml")
    shutil.copyfile(FIXTURE / "simulation.bins", run_directory / "protons.bins")
    shutil.copyfile(FIXTURE / "ordinary.mac", run_directory / "protons.mac")
    shutil.copyfile(
        PHANTOMS / "ramona_zero_0.060MeV_detA_response.txt",
        run_directory / "radiation_phantom0.txt",
    )
    shutil.copyfile(
        PHANTOMS / "ramona_zero_0.060MeV_detA_counting.txt",
        run_directory / "counting_phantom0.txt",
    )
    if chunked:
        shutil.copyfile(FIXTURE / "chunk.mac", run_directory / "protons.chunk.mac")
        (run_directory / "chunks").mkdir()


def invoke_atris(command, run_directory, *arguments, threads="1"):
    environment = os.environ.copy()
    environment["G4FORCENUMBEROFTHREADS"] = threads
    return subprocess.run(
        [command, *arguments],
        cwd=run_directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def run_atris(
    command,
    run_directory,
    simulation,
    *,
    physics="FTFP_BERT_HP",
    mode="-1",
    phantom_count="1",
    threads="1",
):
    return invoke_atris(
        command,
        run_directory,
        physics,
        simulation,
        str(mode),
        str(phantom_count),
        threads=threads,
    )


def histogram_entries(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    data = np.atleast_2d(
        np.loadtxt(path, delimiter=",", skiprows=column_index + 1)
    )
    return int(data[:, 0].sum())


def histogram_annotations(path):
    return {
        fields[1]: fields[2]
        for line in path.read_text().splitlines()
        if line.startswith("#annotation ")
        for fields in [line.split(" ", 2)]
    }


def assert_timing_output(output, worker_threads):
    match = re.search(
        r"### AtRIS timing: Geant4 macro wall time: (\d+\.\d{3}) s "
        r"using (\d+) worker thread\(s\)\n"
        r"### AtRIS timing: setup/cleanup wall time: (\d+\.\d{3}) s\n"
        r"### AtRIS timing: total wall time: (\d+\.\d{3}) s",
        output,
    )
    assert match is not None
    macro_seconds, reported_workers, outside_seconds, total_seconds = match.groups()
    assert int(reported_workers) == worker_threads
    assert float(macro_seconds) >= 0
    assert float(outside_seconds) >= 0
    assert float(total_seconds) == pytest.approx(
        float(macro_seconds) + float(outside_seconds),
        abs=0.002,
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("mode", "creates_interfaces", "creates_steps"),
    [
        pytest.param("-1", False, False, id="csv-response-mode"),
        pytest.param("0", True, False, id="binary-interface-mode"),
        pytest.param("1", True, True, id="binary-step-mode"),
    ],
)
def test_ordinary_prefix_runs_one_worker_and_writes_expected_histograms(
    tmp_path, atris_command, mode, creates_interfaces, creates_steps
):
    prepare_run(tmp_path)

    result = run_atris(atris_command, tmp_path, "protons", mode=mode)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: executing macro protons.mac" in result.stdout
    assert "### AtRIS: Starting the simulation" in result.stdout
    assert "### AtRIS: simulation used 1 worker thread(s)" in result.stdout
    assert "### AtRIS: the simulation has completed" in result.stdout
    assert_timing_output(result.stdout, 1)

    written_suffixes = {
        path.name[len("protons"):]
        for path in tmp_path.glob("protons_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES
    assert histogram_entries(tmp_path / "protons_h1_h1.1.csv") == 2
    for path in tmp_path.glob("protons_*.csv"):
        annotations = histogram_annotations(path)
        assert annotations["atris.csv_schema"] == "1"
        assert annotations["atris.input_prefix"] == "protons"
        assert annotations["atris.physics_list"] == "FTFP_BERT_HP"
        assert annotations["atris.output_mode"] == mode
        assert annotations["atris.random_seed_pairs"] == "runtime-default"
        assert annotations["atris.quantity"]
    assert (tmp_path / "protons.binary").exists() is creates_interfaces
    assert (tmp_path / "protons.steps.binary").exists() is creates_steps
    assert not (tmp_path / "protons.ascii").exists()


@pytest.mark.regression
def test_mode_one_writes_binary_step_trace_with_track_genealogy(
    tmp_path, atris_command
):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        mode="1",
        threads="2",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: simulation used 2 worker thread(s)" in result.stdout
    assert_timing_output(result.stdout, 2)
    records = read_step_records(tmp_path / "protons.steps.binary")
    assert len(records)
    assert set(records["event_id"]) == {0, 1}
    assert np.all(records["track_id"] > 0)
    assert np.all(records["step_id"] > 0)
    assert all(process_name(value) for value in records["creator_process"])
    assert all(process_name(value) for value in records["step_process"])


@pytest.mark.regression
def test_mode_one_contains_mode_zero_interface_records(tmp_path, atris_command):
    mode_zero = tmp_path / "mode-zero"
    mode_one = tmp_path / "mode-one"
    mode_zero.mkdir()
    mode_one.mkdir()
    prepare_run(mode_zero)
    prepare_run(mode_one)

    zero_result = run_atris(atris_command, mode_zero, "protons", mode="0")
    one_result = run_atris(atris_command, mode_one, "protons", mode="1")

    assert zero_result.returncode == 0, zero_result.stdout + zero_result.stderr
    assert one_result.returncode == 0, one_result.stdout + one_result.stderr
    assert (mode_zero / "protons.binary").read_bytes() == (
        mode_one / "protons.binary"
    ).read_bytes()


@pytest.mark.regression
def test_seeded_prefix_uses_shared_chunk_inputs_and_seeded_output_prefix(
    tmp_path, atris_command
):
    prepare_run(tmp_path, chunked=True)
    simulation = "chunks/protons_123456_654321"

    result = run_atris(atris_command, tmp_path, simulation)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: using random seeds 123456 and 654321" in result.stdout
    assert "### AtRIS: executing macro protons.chunk.mac" in result.stdout

    prefix = "protons_123456_654321"
    written_suffixes = {
        path.name[len(prefix):]
        for path in (tmp_path / "chunks").glob(prefix + "_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES
    assert histogram_entries(tmp_path / "chunks" / f"{prefix}_h1_h1.1.csv") == 1
    annotations = histogram_annotations(
        tmp_path / "chunks" / f"{prefix}_h1_h1.1.csv"
    )
    assert annotations["atris.random_seed_pairs"] == "123456:654321"
    assert not (tmp_path / "protons_h1_h1.1.csv").exists()


@pytest.mark.regression
def test_version_form_reports_version_without_simulation_inputs(tmp_path, atris_command):
    result = invoke_atris(atris_command, tmp_path, "--version")

    assert result.returncode == 0
    assert re.fullmatch(r"AtRIS \S+\n", result.stdout)
    assert result.stderr == ""


@pytest.mark.regression
@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param((), id="no-arguments"),
        pytest.param(("FTFP_BERT_HP",), id="too-few-arguments"),
        pytest.param(
            ("FTFP_BERT_HP", "protons", "-1", "1", "extra"),
            id="too-many-arguments",
        ),
    ],
)
def test_wrong_argument_count_prints_usage_and_currently_returns_success(
    tmp_path, atris_command, arguments
):
    result = invoke_atris(atris_command, tmp_path, *arguments)

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "<physics-list> <simulation-name> <mode> <phantom-count>" in result.stdout


@pytest.mark.regression
@pytest.mark.parametrize(
    ("mode", "phantom_count"),
    [
        pytest.param("not-an-integer", "1", id="nonnumeric-mode"),
        pytest.param("-1", "not-an-integer", id="nonnumeric-phantom-count"),
    ],
)
def test_nonnumeric_integer_arguments_exit_nonzero(
    tmp_path, atris_command, mode, phantom_count
):
    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        mode=mode,
        phantom_count=phantom_count,
    )

    assert result.returncode != 0
    assert not list(tmp_path.glob("*.csv"))


@pytest.mark.regression
def test_unsupported_physics_list_exits_nonzero(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        physics="NOT_A_GEANT4_PHYSICS_LIST",
    )

    assert result.returncode != 0
    assert "NOT_A_GEANT4_PHYSICS_LIST is not valid" in result.stdout
    assert "FTFP_BERT_HP" in result.stdout
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
@pytest.mark.parametrize(
    "macro_contents",
    [
        pytest.param(None, id="missing-macro"),
        pytest.param("/not/an/atris/command\n", id="invalid-macro-command"),
    ],
)
def test_missing_or_invalid_macro_exits_nonzero(
    tmp_path, atris_command, macro_contents
):
    prepare_run(tmp_path)
    macro = tmp_path / "protons.mac"
    if macro_contents is None:
        macro.unlink()
    else:
        macro.write_text(macro_contents)

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode != 0
    assert "### AtRIS: macro execution failed with Geant4 status" in result.stderr
    assert "### AtRIS: the simulation has completed" not in result.stdout


@pytest.mark.regression
def test_missing_geometry_exits_nonzero(tmp_path, atris_command):
    prepare_run(tmp_path)
    (tmp_path / "protons.gdml").unlink()

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode != 0
    assert "### AtRIS: the simulation has completed" not in result.stdout


@pytest.mark.regression
def test_missing_energy_bins_currently_runs_with_zero_edges(tmp_path, atris_command):
    prepare_run(tmp_path)
    (tmp_path / "protons.bins").unlink()

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: read 0 binedges." in result.stdout
    assert "### AtRIS: the simulation has completed" in result.stdout
    assert {path.name for path in tmp_path.glob("protons_*.csv")} == {
        "protons_h2_h2.dir.csv",
        "protons_h2_h2.pos.csv",
    }


@pytest.mark.regression
def test_zero_phantom_count_runs_without_phantom_histograms(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        phantom_count="0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    written_suffixes = {
        path.name[len("protons"):]
        for path in tmp_path.glob("protons_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS


@pytest.mark.regression
@pytest.mark.parametrize(
    "mismatched_file",
    ["radiation_phantom1.txt", "counting_phantom1.txt"],
)
def test_mismatched_phantom_pdg_headers_exit_nonzero(
    tmp_path, atris_command, mismatched_file
):
    prepare_run(tmp_path)
    shutil.copyfile(
        tmp_path / "radiation_phantom0.txt",
        tmp_path / "radiation_phantom1.txt",
    )
    shutil.copyfile(
        tmp_path / "counting_phantom0.txt",
        tmp_path / "counting_phantom1.txt",
    )

    path = tmp_path / mismatched_file
    lines = path.read_text().splitlines()
    lines[0] = " ".join(lines[0].split()[:-1])
    path.write_text("\n".join(lines) + "\n")

    result = run_atris(atris_command, tmp_path, "protons", phantom_count="2")

    assert result.returncode != 0
    assert "### AtRIS: PDG header mismatch:" in result.stderr
    assert mismatched_file in result.stderr
    assert "radiation_phantom0.txt" in result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
@pytest.mark.parametrize("mode", ["-2", "2", "999"])
def test_undocumented_integer_modes_currently_follow_csv_path(
    tmp_path, atris_command, mode
):
    prepare_run(tmp_path)

    result = run_atris(atris_command, tmp_path, "protons", mode=mode)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "protons_h1_h1.1.csv").is_file()
    assert not (tmp_path / "protons.binary").exists()


@pytest.mark.regression
def test_negative_phantom_count_currently_behaves_as_zero(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        phantom_count="-1",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: proceeding to load -1 phantom(s)." in result.stdout
    written_suffixes = {
        path.name[len("protons"):]
        for path in tmp_path.glob("protons_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS
