"""Exercise preparation, native phantom chunks, resume, and table statistics."""

import hashlib

import numpy as np
import pytest

from atris_tools.phantom_calibration import (
    RESPONSE_ENERGY_EDGES_MEV,
    PhantomStatistics,
    calibrate_water_phantom,
    compact_water_phantom_chunk,
    prepare_water_phantom,
    read_phantom_statistics,
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
    # Mix a retained old event-record chunk with new compact phantom output.
    assert run_chunks(tmp_path, mode="shower", entry=1) == 1
    first = tmp_path / "chunks" / (chunk_name(read_chunk_plan(tmp_path)[0]) + ".root")
    compact_water_phantom_chunk(first)
    checksum = hashlib.sha256(first.read_bytes()).digest()
    partial = calibrate_water_phantom({2212: tmp_path})
    assert partial.sample_counts.sum() == 256
    assert run_chunks(tmp_path, mode="phantom") == 1
    assert run_chunks(tmp_path, mode="phantom") == 0
    assert hashlib.sha256(first.read_bytes()).digest() == checksum
    response = calibrate_water_phantom({2212: tmp_path})
    statistics = PhantomStatistics.empty()
    for entry in read_chunk_plan(tmp_path):
        statistics += read_phantom_statistics(
            tmp_path / "chunks" / (chunk_name(entry) + ".root")
        )
    count = statistics.sample_counts
    assert count.sum() == 512
    np.testing.assert_array_equal(response.sample_counts[0], count)
    sampled = count > 0
    np.testing.assert_allclose(
        response.energy_fraction[0, sampled], statistics.mean_fraction[sampled]
    )
    np.testing.assert_allclose(
        response.counting_efficiency[0, sampled],
        statistics.detected_counts[sampled] / count[sampled],
    )
    enough = count > 1
    np.testing.assert_allclose(
        response.fraction_variance[0, enough],
        statistics.squared_deviations[enough] / (count[enough] - 1),
        atol=1e-15,
    )
    assert np.all(np.isnan(response.energy_fraction[0, count == 0]))
