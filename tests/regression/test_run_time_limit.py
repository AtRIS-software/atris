"""Native event-boundary time limits preserve complete phantom statistics."""

import re
import shutil
import subprocess

import numpy as np
import pytest
import uproot

from atris_tools.chunks import chunk_name, read_chunk_plan
from atris_tools.phantom_table import ENERGY_EDGES_MEV
from atris_tools.phantom_builder import prepare_phantom_batch
from atris_tools.phantom_statistics import read_phantom_statistics

from test_atris_command import atris_command
from phantom_fixture import water_psf


@pytest.mark.regression
@pytest.mark.parametrize("threads", [1, 3])
def test_time_limit_saves_actual_completed_counts(tmp_path, atris_command, monkeypatch, threads):
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", str(threads))
    monkeypatch.setenv("ATRIS_TIME_LIMIT", "2")
    requested = 1_000_000
    prepare_phantom_batch(
        tmp_path, ENERGY_EDGES_MEV[400:451], psf_path=water_psf(),
        particle="proton", events_per_chunk=requested, chunks=1,
    )
    result = subprocess.run(
        [shutil.which("atris-run"), str(tmp_path), "--mode", "phantom"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    chunk = tmp_path / "chunks" / chunk_name(read_chunk_plan(tmp_path)[0])
    log = chunk.with_suffix(".log").read_text()
    summary = re.search(r"completed (\d+) of (\d+) requested events; time limit reached", log)
    assert summary, log[-5000:]
    completed = int(summary[1])
    assert int(summary[2]) == requested
    assert 0 < completed < requested
    elapsed = float(re.search(r"event-loop wall time: ([\d.e+]+) s", log)[1])
    assert 2 <= elapsed < 30
    assert chunk.with_suffix(".COMPLETE").exists()
    statistics = read_phantom_statistics(chunk.with_suffix(".root"))
    assert statistics.sample_counts.sum() == completed
    assert np.all(statistics.detected_counts <= statistics.sample_counts)
    with uproot.open(chunk.with_suffix(".root")) as root:
        assert root["h1.1"].member("fEntries") == completed
        # Fraction histograms include exactly one complete deposit per event,
        # including events whose deposit is zero, for the one water volume.
        assert root["h2.fraction"].member("fEntries") == completed
        assert root["h2.detected"].member("fEntries") == completed

    # A small event ceiling finishes before the time budget.
    macro = tmp_path / "phantom.chunk.mac"
    source = macro.read_text()
    macro.write_text(source.replace("/run/beamOn 1000000", "/run/beamOn 16"))
    result = subprocess.run(
        [atris_command, "FTFP_BERT_HP", "phantom_123456_654321.root", "3", "0"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "time limit reached" not in result.stdout
    statistics = read_phantom_statistics(tmp_path / "phantom_123456_654321.root")
    assert statistics.sample_counts.sum() == 16


@pytest.mark.regression
def test_event_ceiling_can_finish_before_time_budget(tmp_path, atris_command, monkeypatch):
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "3")
    monkeypatch.setenv("ATRIS_TIME_LIMIT", "60")
    prepare_phantom_batch(tmp_path, ENERGY_EDGES_MEV[400:451], psf_path=water_psf(),
                          particle="proton", events_per_chunk=16, chunks=1)
    result = subprocess.run(
        [atris_command, "FTFP_BERT_HP", "phantom_123456_654321.root", "3", "0"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "completed 16 of 16 requested events; event limit reached" in result.stdout
    assert "time limit: 60 s" in result.stdout
    assert read_phantom_statistics(tmp_path / "phantom_123456_654321.root").sample_counts.sum() == 16


@pytest.mark.regression
@pytest.mark.parametrize("limit", [None, "invalid", "0", "-1", "nan", "inf"])
def test_optional_time_limit_validation(tmp_path, atris_command, monkeypatch, limit):
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "1")
    if limit is None:
        monkeypatch.delenv("ATRIS_TIME_LIMIT", raising=False)
    else:
        monkeypatch.setenv("ATRIS_TIME_LIMIT", limit)
    prepare_phantom_batch(tmp_path, ENERGY_EDGES_MEV[400:451], psf_path=water_psf(),
                          particle="proton", events_per_chunk=16, chunks=1)
    result = subprocess.run(
        [atris_command, "FTFP_BERT_HP", "phantom_123456_654321.root", "3", "0"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    if limit is None:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "completed 16 of 16 requested events; event limit reached" in result.stdout
        assert "time limit: 0 s" in result.stdout
    else:
        assert result.returncode != 0
        assert "ATRIS_TIME_LIMIT must be a finite positive number" in result.stdout + result.stderr
