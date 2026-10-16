"""Exercise phantom preparation, native chunks, resume, and statistics."""

import hashlib
import json

import numpy as np
import pytest

from atris_tools.phantom_table import ENERGY_EDGES_MEV
from atris_tools.phantom_statistics import (
    PhantomStatistics,
    compact_phantom_chunk,
    read_phantom_statistics,
)
from atris_tools.phantom import Phantom
from atris_tools.phantom_builder import prepare_phantom_batch
from atris_tools.chunks import chunk_name, read_chunk_plan
from atris_tools.run_chunks import run_chunks
from atris_tools.phantom_builder import PhantomBuilder
from atris_tools.psf import PSF

from test_atris_command import atris_command
from phantom_fixture import water_psf


@pytest.mark.regression
def test_native_chunks_feed_phantom_and_resume(
    tmp_path, atris_command, monkeypatch
):
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "2")
    prepare_phantom_batch(
        tmp_path,
        ENERGY_EDGES_MEV[150:351],
        psf_path=water_psf(4e-4),
        production_cut_mm=1e-5,
        tracking_floor_eV=1,
        particle="proton",
        events_per_chunk=256,
        chunks=2,
    )
    # Mix a retained old event-record chunk with new compact phantom output.
    assert run_chunks(tmp_path, mode="shower", entry=1) == 1
    first = tmp_path / "chunks" / (chunk_name(read_chunk_plan(tmp_path)[0]) + ".root")
    compact_phantom_chunk(first)
    checksum = hashlib.sha256(first.read_bytes()).digest()
    sphere = PSF(inner_radius_km=0, outer_radius_km=4e-9,
                 temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                 mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
                 solid_composition="H112O888", state="liquid")
    builder = PhantomBuilder(sphere, [22, 2212], directory=tmp_path / "build",
                             name="native-test", production_cut_mm=1e-5, tracking_floor_eV=1)
    records = []
    for index, entry in enumerate(read_chunk_plan(tmp_path)):
        directory = builder.directory / "batches" / f"batch-{index:06d}"
        directory.mkdir(parents=True)
        (directory / "chunks.txt").write_text(" ".join(map(str, entry)) + "\n")
        (directory / "chunks").symlink_to(tmp_path / "chunks", target_is_directory=True)
        records.append(dict(pdg=2212, directory=str(directory.relative_to(builder.directory))))
    (builder.directory / "batches.json").write_text(json.dumps(records))
    partial = builder.gather()
    assert partial.sample_counts.sum() == 256
    assert run_chunks(tmp_path, mode="phantom") == 1
    assert run_chunks(tmp_path, mode="phantom") == 0
    assert hashlib.sha256(first.read_bytes()).digest() == checksum
    response = builder.gather()
    statistics = PhantomStatistics.empty()
    for entry in read_chunk_plan(tmp_path):
        statistics += read_phantom_statistics(
            tmp_path / "chunks" / (chunk_name(entry) + ".root")
        )
    count = statistics.sample_counts
    assert count.sum() == 512
    np.testing.assert_array_equal(response.sample_counts[1], count)
    sampled = count > 0
    np.testing.assert_allclose(
        response.energy_fraction[1, sampled], statistics.mean_fraction[sampled]
    )
    np.testing.assert_allclose(
        response.counting_efficiency[1, sampled],
        statistics.detected_counts[sampled] / count[sampled],
    )
    enough = count > 1
    np.testing.assert_allclose(
        response.fraction_variance[1, enough],
        statistics.squared_deviations[enough] / (count[enough] - 1),
        atol=1e-15,
    )
    assert np.all(np.isnan(response.energy_fraction[1, count == 0]))
