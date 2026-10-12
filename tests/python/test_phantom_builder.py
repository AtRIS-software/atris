import json
import signal
import subprocess

import numpy as np
import pytest

from atris_tools.phantom_builder import PhantomBuild
from atris_tools.phantom_calibration import PhantomStatistics
from atris_tools.psf import build_psf, write_psf


def water_psf(path, radius_cm=15):
    psf = build_psf(inner_radius_km=[0], outer_radius_km=[radius_cm / 1e5],
                    temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                    mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
                    solid_composition="H112O888", state="liquid")
    write_psf(path, psf)


@pytest.fixture
def build(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path, .0004)
    return PhantomBuild.prepare(tmp_path / "run", path, [22, 2212])


def test_prepare_psf_idempotent_and_preserves_micrometre_radius(build):
    assert build.settings["radius_cm"] == pytest.approx(.0004)
    reopened = PhantomBuild.prepare(build.directory, build.directory / "simulation.psf", [22, 2212])
    assert reopened.settings == build.settings
    with pytest.raises(FileExistsError):
        PhantomBuild.prepare(build.directory, build.directory / "simulation.psf", [22, 2212], pilot_events=10)
    assert build._batches() == []


def test_rejects_changed_geometry_and_nonwater(tmp_path, build):
    with (build.directory / "simulation.psf").open("a") as output:
        output.write("# changed\n")
    with pytest.raises(ValueError, match="PSF changed"):
        PhantomBuild.open(build.directory)
    path = tmp_path / "solid.psf"
    psf = build_psf(inner_radius_km=[0], outer_radius_km=[1e-5], temperature_k=293,
                    density_g_cm3=2.7, pressure_pa=0, mass_fractions={"Al": 1},
                    solid_composition="Al1000", state="solid")
    write_psf(path, psf)
    with pytest.raises(ValueError, match="liquid H2O"):
        PhantomBuild.prepare(tmp_path / "aluminium", path, [22])


def test_missing_and_zero_response_are_unresolved(build):
    response = build.response()
    assert np.isnan(response.energy_fraction).all()
    assert not build.precision(response)["resolved"].any()
    response.sample_counts[:] = 100
    response.energy_fraction[:] = 0
    response.fraction_standard_error[:] = 0
    assert not build.precision(response)["passed"].any()
    response.energy_fraction[:] = .5
    response.fraction_standard_error[:] = .001
    assert build.precision(response)["passed"].all()


def test_batches_are_bounded_completed_inputs_preserved_and_pending_resumed(build, monkeypatch):
    def complete(self, batch, threads):
        self._chunk(batch).with_suffix(".COMPLETE").touch()
        batch.update(threads=threads, wall_seconds=10, fit_timing=True)

    stats = PhantomStatistics(np.full(650, 2), np.full(650, .5), np.full(650, .1), np.ones(650, dtype=int))
    monkeypatch.setattr(PhantomBuild, "_execute", complete)
    monkeypatch.setattr("atris_tools.phantom_builder.read_phantom_statistics", lambda path: stats)
    monkeypatch.setattr("atris_tools.phantom_builder.read_ntuple", lambda *args: {
        "physics_list": ["FTFP_BERT_HP"], "atris_version": ["test-version"]})
    build.run(batches=2)
    before = build._batches()
    assert [b["pdg"] for b in before] == [22, 2212]
    assert build.response().sample_counts.sum() == 2600
    assert build.response().metadata["atris_version"] == "test-version"
    inputs = (build.directory / before[0]["directory"] / "chunks.txt").read_bytes()
    build.run(batches=1, adaptive=True)
    assert (build.directory / before[0]["directory"] / "chunks.txt").read_bytes() == inputs
    assert len(build._batches()) == 3

    pending = build._batches()[-1]
    assert pending["decades"] == 1
    assert pending["reason"] == "exploration"
    build._chunk(pending).with_suffix(".COMPLETE").unlink()
    build.run(batches=1, adaptive=True)
    assert len(build._batches()) == 3
    monkeypatch.setattr("atris_tools.phantom_builder.read_ntuple", lambda *args: {
        "physics_list": ["QGSP_BERT"], "atris_version": ["test-version"]})
    with pytest.raises(ValueError, match="physics list differs"):
        build.response()


def test_lock_prevents_duplicate_builder_and_releases(build):
    with build._lock():
        with pytest.raises(RuntimeError, match="Another builder"):
            with build._lock():
                pass
    with build._lock():
        pass


def test_postprocess_retains_partial_arrays_and_reports_unresolved(build):
    response = build.postprocess()
    state = json.loads((build.directory / "export/sampling-state.json").read_text())
    assert state["resolved_bins"] == 0
    assert not state["precision_complete"]
    assert not state["counting_drives_sampling"]
    assert (build.directory / "export/diagnostics.png").exists()
    assert (build.directory / "export/sampling-precision.png").exists()
    with np.load(build.directory / "export/water-sphere_sampling.npz") as arrays:
        np.testing.assert_array_equal(arrays["sample_counts"], response.sample_counts)


def test_prepare_does_not_overwrite_orphaned_batch_records(tmp_path):
    path = tmp_path / "water.psf"
    water_psf(path)
    records = tmp_path / "batches.json"
    records.write_text('[{"retained": true}]')
    with pytest.raises(FileExistsError, match="original build configuration"):
        PhantomBuild.prepare(tmp_path, path, [22])
    assert records.read_text() == '[{"retained": true}]'


def test_interruption_stops_process_group_and_preserves_partial_output(build, monkeypatch):
    def interrupt(self, batch, threads):
        chunk = self._chunk(batch)
        chunk.with_suffix(".root").write_bytes(b"partial ROOT")
        raise KeyboardInterrupt

    monkeypatch.setattr(PhantomBuild, "_execute", interrupt)
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
    assert killed == [(12345, signal.SIGTERM)]
    assert not original.exists()
    archived = list(original.parent.parent.glob("interrupted-*/*.root"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == b"partial ROOT"
    assert len(build._batches()) == 1
    with build._lock():
        pass
