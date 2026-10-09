"""Exercise preparation, native phantom chunks, resume, and table statistics."""

import hashlib

import numpy as np
import pytest

from atris_tools.phantom_calibration import (
    RESPONSE_ENERGY_EDGES_MEV,
    calibrate_water_phantom,
    prepare_water_phantom,
    read_water_phantom_events,
)
from atris_tools.gather import chunk_name, read_chunk_plan
from atris_tools.run_chunks import run_chunks

from test_atris_command import atris_command


@pytest.mark.regression
def test_native_chunks_feed_calibration_and_resume(
    tmp_path, atris_command, monkeypatch
):
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "2")
    prepare_water_phantom(
        tmp_path,
        RESPONSE_ENERGY_EDGES_MEV[150:351],
        radius_cm=4e-4,
        production_cut_mm=1e-5,
        tracking_floor_eV=1,
        particle="proton",
        events_per_chunk=256,
        chunks=2,
    )
    assert run_chunks(tmp_path, mode="phantom", entry=1) == 1
    first = tmp_path / "chunks" / (chunk_name(read_chunk_plan(tmp_path)[0]) + ".root")
    checksum = hashlib.sha256(first.read_bytes()).digest()
    partial = calibrate_water_phantom({2212: tmp_path})
    assert partial.sample_counts.sum() == 256
    assert run_chunks(tmp_path, mode="phantom") == 1
    assert run_chunks(tmp_path, mode="phantom") == 0
    assert hashlib.sha256(first.read_bytes()).digest() == checksum
    response = calibrate_water_phantom({2212: tmp_path})
    events = read_water_phantom_events(tmp_path)
    assert len(events.incident_energy_MeV) == 512
    count = np.histogram(events.incident_energy_MeV, RESPONSE_ENERGY_EDGES_MEV)[0]
    np.testing.assert_array_equal(response.sample_counts[0], count)
    fraction = events.ionizing_energy_MeV / events.incident_energy_MeV
    bins = np.searchsorted(RESPONSE_ENERGY_EDGES_MEV, events.incident_energy_MeV) - 1
    for index in np.flatnonzero(count > 1):
        samples = fraction[bins == index]
        np.testing.assert_allclose(response.energy_fraction[0, index], samples.mean())
        np.testing.assert_allclose(
            response.fraction_variance[0, index], samples.var(ddof=1), atol=1e-15
        )
        assert response.counting_efficiency[0, index] == np.count_nonzero(
            samples > 0
        ) / len(samples)
    assert np.all(np.isnan(response.energy_fraction[0, count == 0]))
