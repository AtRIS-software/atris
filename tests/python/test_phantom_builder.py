import json
import signal
import subprocess
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pytest

from atris_tools.phantom_builder import PhantomBuilder
from atris_tools.phantom_calibration import Phantom, PhantomStatistics
from atris_tools.psf import PSF, write_psf


def water_psf(path, radius_cm=15):
    psf = PSF(inner_radius_km=[0], outer_radius_km=[radius_cm / 1e5],
                    temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                    mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
                    solid_composition="H112O888", state="liquid")
    write_psf(path, psf)
    return psf


@pytest.fixture
def build(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path, .0004)
    return PhantomBuilder(path, [22, 2212], directory=tmp_path / "run")


def test_species_specific_pilots_round_trip(tmp_path):
    psf = water_psf(tmp_path / "sphere.psf")
    builder = PhantomBuilder(psf, ["photon", "proton"], directory=tmp_path / "run",
                             pilot_events={"photon": 500000, "proton": 100000})
    reopened = PhantomBuilder.open(builder.directory)
    response = Phantom.gather(directory=builder.directory)
    first = reopened._select([], response, 3, True)
    second = reopened._select([{"pdg": 22}], response, 3, True)
    assert first[3] == 500000
    assert second[3] == 100000
    assert "photon 5.000e+05" in str(reopened)


def test_species_specific_pilots_require_all_species(tmp_path):
    psf = water_psf(tmp_path / "sphere.psf")
    with pytest.raises(ValueError, match="every configured species"):
        PhantomBuilder(psf, ["photon", "proton"], directory=tmp_path / "run",
                       pilot_events={"photon": 500000})


def test_prepare_defaults_to_current_folder(tmp_path, monkeypatch):
    psf = water_psf(tmp_path / "water.psf")
    monkeypatch.chdir(tmp_path)
    builder = PhantomBuilder(psf=psf, pdg_codes=["photon"], name="example")
    assert builder.directory == tmp_path
    assert (tmp_path / "phantom-build.json").exists()
    assert builder.settings["stem"] == "example"
    assert not (tmp_path / "example.psf").exists()
    assert (tmp_path / "simulation.psf").exists()
    assert Phantom.gather().metadata == Phantom.gather(directory=tmp_path).metadata
    assert Phantom.gather("example").metadata == Phantom.gather(directory=tmp_path).metadata
    assert Phantom.gather("example", directory=tmp_path).metadata == Phantom.gather().metadata
    with pytest.raises(ValueError, match="contains phantom 'example', not 'other'"):
        Phantom.gather("other")


def test_run_logs_full_current_folder(build, monkeypatch, caplog):
    monkeypatch.chdir(build.directory)
    monkeypatch.setattr(PhantomBuilder, "_select", lambda *args: None)
    caplog.set_level("INFO", logger="atris_tools.phantom_builder")
    build.run()
    assert f"Running phantom sampling in folder {build.directory}" in caplog.text


def test_show_schedule_after_preparation_is_read_only(build, capsys):
    before = {path.relative_to(build.directory): path.read_bytes()
              for path in build.directory.rglob("*") if path.is_file()}
    assert build.show_schedule(batches=4, threads=3) is None
    output = capsys.readouterr().out
    rows = [line.split() for line in output.splitlines()[2:]]
    assert [row[1] for row in rows] == ["photon", "proton", "photon", "proton"]
    assert all(row[4] == "1.300e+03" and float(row[2]) < float(row[3]) for row in rows)
    assert output.count("initial coverage") == 2
    assert output.count("batch count") == 2
    assert "user requested" not in output
    assert "threads" not in output
    assert "Later adaptive" not in output
    build.show_schedule(batches=8, adaptive=True, threads=3)
    output = capsys.readouterr().out
    assert "Schedule preview: 8 batches" in output
    assert "Preview uses current statistics" in output
    assert output.count("insufficient samples") == 6
    after = {path.relative_to(build.directory): path.read_bytes()
             for path in build.directory.rglob("*") if path.is_file()}
    assert after == before
    build.show_schedule()
    assert "Schedule preview: 2 batches" in capsys.readouterr().out


@pytest.mark.parametrize("kwargs", [{"batches": 0}, {"threads": 0}, {"batches": 1.5}])
def test_show_schedule_validates_counts(build, kwargs):
    with pytest.raises(ValueError, match="positive integers"):
        build.show_schedule(**kwargs)


@pytest.mark.parametrize("time_limit_s", [0, -1, float("nan"), float("inf")])
def test_show_schedule_validates_time_limit(build, time_limit_s):
    with pytest.raises(ValueError, match="time_limit_s"):
        build.show_schedule(time_limit_s=time_limit_s)


def test_show_schedule_passes_budget_without_saving_batches(build, monkeypatch, capsys):
    select = PhantomBuilder._select
    limits = []

    def capture(self, batches, response, threads, adaptive, time_limit_s):
        limits.append(time_limit_s)
        return select(self, batches, response, threads, adaptive, time_limit_s)

    monkeypatch.setattr(PhantomBuilder, "_select", capture)
    before = build._batches()
    build.show_schedule(batches=3, adaptive=True, time_limit_s=60)
    assert limits == [60, 60, 60]
    assert "Schedule preview: 3 batches" in capsys.readouterr().out
    assert build._batches() == before


@pytest.mark.parametrize("count,error,resolved,timed,periodic,reason", [
    (1, np.nan, False, False, False, "insufficient samples"),
    (2, np.nan, False, False, False, "unresolved uncertainty"),
    (2, 0.0, False, False, False, "zero deposit"),
    (2, 0.1, True, False, False, "timing pilot"),
    (2, 0.1, True, True, False, "precision"),
    (2, 0.1, True, True, True, "coverage"),
])
def test_adaptive_selection_explains_reason(build, monkeypatch, count, error,
                                          resolved, timed, periodic, reason):
    shape = (2, 650)
    passed = np.ones(shape, dtype=bool)
    passed[0, :50] = False
    quality = dict(passed=passed, resolved=np.full(shape, resolved),
                   dose_error=np.full(shape, error), ratio=np.full(shape, 2.0))
    monkeypatch.setattr(PhantomBuilder, "precision", lambda *args: quality)
    response = SimpleNamespace(sample_counts=np.full(shape, count))
    records = [dict(pdg=code, first_decade=0, decades=13)
               for code in build.settings["pdg_codes"]]
    if timed:
        records.append(dict(pdg=22, first_decade=0, decades=1, threads=2,
                            fit_timing=True, events=1300, wall_seconds=10))
    if periodic:
        records.append(records[1].copy())
    selected = build._select(records, response, threads=2, adaptive=True)
    assert selected[4] == reason


def test_prepare_accepts_psf_object(tmp_path):
    psf = water_psf(tmp_path / "water.psf")
    builder = PhantomBuilder(psf, ["photon"], directory=tmp_path / "run")
    assert (builder.directory / "simulation.psf").read_bytes() == (tmp_path / "water.psf").read_bytes()
    assert PhantomBuilder(psf, ["photon"], directory=builder.directory).settings == builder.settings
    changed = PSF(inner_radius_km=0, outer_radius_km=1e-4,
                        temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                        mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
                        state="liquid")
    with pytest.raises(FileExistsError):
        PhantomBuilder(changed, ["photon"], directory=builder.directory)


def test_tracking_floor_retained_in_new_batch(build, tmp_path, monkeypatch):
    builder = PhantomBuilder(build.directory / "simulation.psf", ["photon"],
                             directory=tmp_path / "tracking-floor", tracking_floor_eV=1)

    def stop_before_transport(self, batch, threads):
        raise RuntimeError("prepared input")

    monkeypatch.setattr(PhantomBuilder, "_execute", stop_before_transport)
    with pytest.raises(RuntimeError, match="prepared input"):
        builder.run()
    assert PhantomBuilder.open(builder.directory).settings["tracking_floor_eV"] == 1
    macro = (builder.directory / builder._batches()[0]["directory"] / "calibration.chunk.mac").read_text()
    for command in ("/process/em/lowestElectronEnergy", "/process/em/lowestMuHadEnergy"):
        line = next(line for line in macro.splitlines() if line.startswith(command))
        assert float(line.split()[1]) == 1


@pytest.mark.parametrize("floor", [-1, float("nan"), float("inf")])
def test_tracking_floor_validation(build, tmp_path, floor):
    with pytest.raises(ValueError, match="tracking_floor_eV"):
        PhantomBuilder(build.directory / "simulation.psf", ["photon"],
                       directory=tmp_path / "invalid-floor", tracking_floor_eV=floor)


def test_prepare_psf_idempotent_and_preserves_micrometre_radius(build):
    assert build.radius_cm == pytest.approx(.0004)
    assert "radius_cm" not in build.settings
    assert "density_g_cm3" not in build.settings
    reopened = PhantomBuilder(build.directory / "simulation.psf", [22, 2212], directory=build.directory)
    assert reopened.settings == build.settings
    with pytest.raises(FileExistsError):
        PhantomBuilder(build.directory / "simulation.psf", [22, 2212], directory=build.directory, pilot_events=10)
    assert build._batches() == []


def test_prepare_accepts_species_names(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path)
    names = ["photon", 2212, (26, 56), ("nickel", 58), "Fe-56", "iron-56", ("Fe", 56)]
    calibration = PhantomBuilder(path, names, directory=tmp_path / "run")
    assert calibration.settings["pdg_codes"] == [22, 2212, 1000260560, 1000280580]
    reopened = PhantomBuilder(path, calibration.settings["pdg_codes"],
                                     directory=tmp_path / "run")
    assert reopened.settings == calibration.settings


def test_name_controls_saved_filenames(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path)
    builder = PhantomBuilder(path, ["photon"], directory=tmp_path / "run", name="example")
    assert "Phantom sampling: example" in str(builder)
    phantom = Phantom.gather(directory=builder.directory)
    phantom.save(tmp_path / "export", allow_partial=True)
    assert (tmp_path / "export/example_sampling.root").exists()
    phantom.save(tmp_path / "renamed", name="another", allow_partial=True)
    assert (tmp_path / "renamed/another_sampling.root").exists()
    assert Phantom.read_root(tmp_path / "renamed/another_sampling.root").metadata["phantom"] == "another"


def test_relative_dose_tolerance_reads_existing_run_without_rewriting(build):
    path = build.directory / "phantom-build.json"
    previous = dict(build.settings)
    previous["relative_tolerance"] = previous.pop("relative_dose_tolerance")
    path.write_text(json.dumps(previous))
    original = path.read_bytes()
    reopened = PhantomBuilder.open(build.directory)
    assert reopened.settings["relative_dose_tolerance"] == .05
    assert "relative_tolerance" not in reopened.settings
    phantom = Phantom.gather(directory=build.directory)
    assert phantom.metadata["precision_settings"]["relative_dose_tolerance"] == .05
    assert path.read_bytes() == original


def test_relative_dose_tolerance_parameter(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path)
    builder = PhantomBuilder(path, ["photon"], directory=tmp_path / "run",
                                     dose_rtol=.02, dose_atol_Gy=2e-12)
    phantom = Phantom.gather(directory=builder.directory)
    assert phantom.metadata["precision_settings"]["relative_dose_tolerance"] == .02
    assert phantom.metadata["precision_settings"]["absolute_dose_tolerance_Gy"] == 2e-12
    assert "Relative dose tolerance: 2.0%" in str(builder)


def test_rejects_changed_geometry_and_nonwater(tmp_path, build):
    with (build.directory / "simulation.psf").open("a") as output:
        output.write("# changed\n")
    with pytest.raises(ValueError, match="PSF changed"):
        PhantomBuilder.open(build.directory)
    with pytest.raises(ValueError, match="PSF changed"):
        Phantom.gather(directory=build.directory)
    path = tmp_path / "solid.psf"
    psf = PSF(inner_radius_km=[0], outer_radius_km=[1e-5], temperature_k=293,
                    density_g_cm3=2.7, pressure_pa=0, mass_fractions={"Al": 1},
                    solid_composition="Al1000", state="solid")
    write_psf(path, psf)
    with pytest.raises(ValueError, match="liquid H2O"):
        PhantomBuilder(path, [22], directory=tmp_path / "aluminium")


def test_missing_and_zero_response_are_unresolved(build):
    response = Phantom.gather(directory=build.directory)
    assert np.isnan(response.energy_fraction).all()
    assert not build.precision(response)["resolved"].any()
    response.sample_counts[:] = 100
    response.energy_fraction[:] = 0
    response.fraction_standard_error[:] = 0
    assert not build.precision(response)["passed"].any()
    response.energy_fraction[:] = .5
    response.fraction_standard_error[:] = .001
    assert build.precision(response)["passed"].all()


def test_readable_build_and_response_summaries(build):
    assert "Species: photon, proton" in str(build)
    assert "Primaries per pilot: photon 1.300e+03, proton 1.300e+03" in str(build)
    assert "Relative dose tolerance: 5.0%" in str(build)
    response = Phantom.gather(directory=build.directory)
    assert "Primaries retained: 0" in str(response)
    assert "Sampled bins: 0/1,300" in str(response)
    assert "Passing energy bins: 0" in str(response)
    assert "Precision complete: False" in str(response)


@pytest.mark.parametrize("completed", [0, 100, 1300])
@pytest.mark.parametrize("time_limit", [None, 2.5])
def test_timing_fit_uses_actual_completed_counts(build, monkeypatch, completed, time_limit):
    monkeypatch.setenv("ATRIS_TIME_LIMIT", "999")
    response = Phantom.gather(directory=build.directory)
    monkeypatch.setattr(Phantom, "gather", lambda **kwargs: response)
    monkeypatch.setattr("atris_tools.phantom_builder.shutil.which", lambda name: name)
    monkeypatch.setattr("atris_tools.phantom_builder.read_phantom_statistics", lambda path:
                        SimpleNamespace(sample_counts=np.array([completed])))

    def launch(*args, **kwargs):
        assert kwargs["env"].get("ATRIS_TIME_LIMIT") == (str(time_limit) if time_limit else None)
        batch = build._batches()[-1]
        build._chunk(batch).with_suffix(".COMPLETE").touch()
        build._chunk(batch).with_suffix(".log").write_text("event-loop wall time: 2.5 s")
        return SimpleNamespace(poll=lambda: 0, returncode=0)

    monkeypatch.setattr(subprocess, "Popen", launch)
    build.run(time_limit_s=time_limit)
    batch = build._batches()[0]
    assert batch["events"] == 1300
    assert batch["completed_events"] == completed
    assert batch["fit_timing"] == (completed > 0)
    assert batch["event_loop_seconds"] == 2.5
    assert batch["time_limit_seconds"] == time_limit


@pytest.mark.parametrize("time_limit_s,events,forecast", [(1, 1300, 3), (None, 80000, 82)])
def test_adaptive_forecast_uses_completed_counts_and_budget(build, monkeypatch,
                                                          time_limit_s, events, forecast):
    shape = (2, 650)
    passed = np.ones(shape, dtype=bool)
    passed[0, :100] = False
    quality = dict(passed=passed, resolved=np.ones(shape, dtype=bool),
                   dose_error=np.ones(shape), ratio=np.full(shape, 2.0))
    monkeypatch.setattr(PhantomBuilder, "precision", lambda *args: quality)
    response = SimpleNamespace(sample_counts=np.full(shape, 100))
    records = [dict(pdg=code, first_decade=0, decades=13)
               for code in build.settings["pdg_codes"]]
    records.extend([
        dict(pdg=22, first_decade=0, decades=1, threads=3, fit_timing=True,
             events=100_000_000, completed_events=1000, event_loop_seconds=10, wall_seconds=12),
        dict(pdg=22, first_decade=1, decades=1, threads=3, fit_timing=True,
             events=100_000, completed_events=10000, event_loop_seconds=10, wall_seconds=12),
        records[1].copy(),
    ])
    selected = build._select(records, response, threads=3, adaptive=True, time_limit_s=time_limit_s)
    assert selected[:5] == (22, 1, 1, events, "precision")
    assert selected[5] == pytest.approx(forecast)


@pytest.mark.parametrize("threads,width,fit,completed,duration", [
    (2, 1, True, 100, 10), (3, 13, True, 100, 10),
    (3, 1, False, 100, 10), (3, 1, True, 0, 10), (3, 1, True, 100, 0),
])
def test_adaptive_ignores_unmatched_or_unusable_timings(build, monkeypatch,
                                                     threads, width, fit, completed, duration):
    shape = (2, 650)
    passed = np.ones(shape, dtype=bool)
    passed[0, :50] = False
    monkeypatch.setattr(PhantomBuilder, "precision", lambda *args: dict(
        passed=passed, resolved=np.ones(shape, dtype=bool),
        dose_error=np.ones(shape), ratio=np.full(shape, 2.0)))
    records = [dict(pdg=code, first_decade=0, decades=13)
               for code in build.settings["pdg_codes"]]
    records.append(dict(pdg=22, first_decade=0, decades=width, threads=threads,
                        fit_timing=fit, events=1000, completed_events=completed,
                        event_loop_seconds=duration, wall_seconds=12))
    selected = build._select(records, SimpleNamespace(sample_counts=np.full(shape, 100)),
                             threads=3, adaptive=True, time_limit_s=1)
    assert selected[4] == "timing pilot"
    assert selected[5] is None


@pytest.mark.parametrize("time_limit", [0, -1, float("nan"), float("inf")])
def test_invalid_time_limit_leaves_batches_unchanged(build, time_limit):
    before = build._batches()
    with pytest.raises(ValueError, match="time_limit"):
        build.run(time_limit_s=time_limit)
    assert build._batches() == before


@pytest.mark.parametrize("time_limit", [None, 2.5])
def test_time_limit_passed_to_native_and_saved_before_launch(build, monkeypatch, time_limit):
    monkeypatch.setenv("ATRIS_TIME_LIMIT", "999")
    monkeypatch.setattr("atris_tools.phantom_builder.shutil.which", lambda name: name)

    def launch(*args, **kwargs):
        assert kwargs["env"].get("ATRIS_TIME_LIMIT") == (str(time_limit) if time_limit else None)
        assert build._batches()[-1]["time_limit_seconds"] == time_limit
        raise RuntimeError("captured launch")

    monkeypatch.setattr("atris_tools.phantom_builder.subprocess.Popen", launch)
    with pytest.raises(RuntimeError, match="captured launch"):
        build.run(time_limit_s=time_limit)


def test_batches_are_bounded_completed_inputs_preserved_and_pending_resumed(build, monkeypatch, caplog, capsys):
    caplog.set_level("INFO", logger="atris_tools.phantom_builder")
    def complete(self, batch, threads):
        self._chunk(batch).with_suffix(".COMPLETE").touch()
        batch.update(threads=threads, wall_seconds=10, fit_timing=True)

    stats = PhantomStatistics(np.full(650, 2), np.full(650, .5), np.full(650, .1), np.ones(650, dtype=int))
    monkeypatch.setattr(PhantomBuilder, "_execute", complete)
    monkeypatch.setattr("atris_tools.phantom_calibration.read_phantom_statistics", lambda path: stats)
    monkeypatch.setattr("atris_tools.phantom_calibration.read_ntuple", lambda *args: {
        "physics_list": ["FTFP_BERT_HP"], "atris_version": ["test-version"]})
    build.run(batches=2)
    assert f"Running phantom sampling in folder {build.directory}" in caplog.text
    assert "Batches: 2; transport threads per batch: 1" in caplog.text
    assert f"atris-build-phantom {build.directory} --batches 2 --threads 1" in caplog.text
    before = build._batches()
    assert [b["pdg"] for b in before] == [22, 2212]
    assert Phantom.gather(directory=build.directory).sample_counts.sum() == 2600
    assert Phantom.gather(directory=build.directory).metadata["atris_version"] == "test-version"
    phantom = Phantom.gather(directory=build.directory)
    phantom.save(build.directory / "export", allow_partial=True)
    restored = Phantom.read_root(build.directory / "export/water-sphere_sampling.root")
    for field in fields(Phantom):
        original = getattr(phantom, field.name)
        saved = getattr(restored, field.name)
        if field.name == "metadata":
            for key, value in original.items():
                assert saved[key] == value
        else:
            np.testing.assert_array_equal(saved, original)
    inputs = (build.directory / before[0]["directory"] / "chunks.txt").read_bytes()
    build.show_schedule(batches=4, adaptive=True)
    preview = capsys.readouterr().out
    assert "Schedule preview: 4 batches" in preview
    assert "timing pilot" in preview
    assert "Preview uses current statistics" in preview
    build.run(batches=1, adaptive=True)
    assert "--threads 1 --adaptive" in caplog.text
    assert (build.directory / before[0]["directory"] / "chunks.txt").read_bytes() == inputs
    assert len(build._batches()) == 3

    pending = build._batches()[-1]
    assert pending["decades"] == 1
    assert pending["reason"] == "timing pilot"
    build._chunk(pending).with_suffix(".COMPLETE").unlink()
    build.show_schedule(batches=4, adaptive=True)
    preview = capsys.readouterr().out
    assert "resume" in preview
    assert f"{pending['events']:.3e}" in preview
    assert "Schedule preview: 4 batches" in preview
    build.run(batches=1, adaptive=True)
    assert len(build._batches()) == 3
    monkeypatch.setattr("atris_tools.phantom_calibration.read_ntuple", lambda *args: {
        "physics_list": ["QGSP_BERT"], "atris_version": ["test-version"]})
    with pytest.raises(ValueError, match="physics list differs"):
        Phantom.gather(directory=build.directory)


def test_lock_prevents_duplicate_builder_and_releases(build):
    with build._lock():
        with pytest.raises(RuntimeError, match="Another builder"):
            with build._lock():
                pass
    with build._lock():
        pass


def test_gather_and_save_are_separate_and_preserve_all_fields(build, monkeypatch):
    response = Phantom.gather(directory=build.directory)
    assert not (build.directory / "export").exists()
    monkeypatch.chdir(build.directory)
    response.save()
    assert not (build.directory / "export").exists()
    assert not (build.directory / "water-sphere_diagnostics.png").exists()
    state = json.loads((build.directory / "water-sphere_sampling-state.json").read_text())
    assert state["resolved_bins"] == 0
    assert not state["precision_complete"]
    assert not state["counting_drives_sampling"]
    retained = Phantom.read_root(build.directory / "water-sphere_sampling.root")
    for field in fields(Phantom):
        original = getattr(response, field.name)
        restored = getattr(retained, field.name)
        if field.name == "metadata":
            for key, value in original.items():
                assert restored[key] == value
        else:
            np.testing.assert_array_equal(restored, original)
    assert retained.metadata["geometry_psf"] == (build.directory / "simulation.psf").read_text()
    assert retained.metadata["precision_settings"]["relative_dose_tolerance"] == build.settings["relative_dose_tolerance"]
    assert retained.metadata["sampling_settings"] == build.settings
    assert not (build.directory / "water-sphere_sampling.npz").exists()


def test_prepare_does_not_overwrite_orphaned_batch_records(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path)
    records = tmp_path / "batches.json"
    records.write_text('[{"retained": true}]')
    with pytest.raises(FileExistsError, match="original build configuration"):
        PhantomBuilder(path, [22], directory=tmp_path)
    assert records.read_text() == '[{"retained": true}]'


def test_interruption_stops_process_group_and_preserves_partial_output(build, monkeypatch, caplog):
    caplog.set_level("INFO", logger="atris_tools.phantom_builder")
    def interrupt(self, batch, threads):
        chunk = self._chunk(batch)
        chunk.with_suffix(".root").write_bytes(b"partial ROOT")
        raise KeyboardInterrupt

    monkeypatch.setattr(PhantomBuilder, "_execute", interrupt)
    with pytest.raises(KeyboardInterrupt):
        build.run()
    batch = build._batches()[0]
    original = build._chunk(batch).with_suffix(".root")
    monkeypatch.undo()
    monkeypatch.setattr("atris_tools.phantom_builder.shutil.which", lambda name: name)
    killed = []
    class Process:
        pid = 12345
        args = ["atris-run"]
        def poll(self):
            raise KeyboardInterrupt
        def wait(self, timeout=None):
            return -signal.SIGTERM
    def launch(args, **kwargs):
        assert kwargs["start_new_session"]
        assert kwargs["env"]["G4FORCENUMBEROFTHREADS"] == "2"
        return Process()
    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr("atris_tools.phantom_builder.os.killpg", lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(KeyboardInterrupt):
        build.run(threads=2)
    assert ("Simulating up to 1.300e+03 primaries of photon (PDG 22) with kinetic energies "
            "from 1.000e-06 to 1.000e+07 MeV to sample this species across the full energy range.") in caplog.text
    assert killed == [(12345, signal.SIGTERM)]
    assert not original.exists()
    archived = list(original.parent.parent.glob("interrupted-*/*.root"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == b"partial ROOT"
    assert len(build._batches()) == 1
    with build._lock():
        pass
