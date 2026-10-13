"""Compare fixed-size phantom statistics with detailed shower records."""

import numpy as np
import pytest
import uproot

from test_atris_command import atris_command, invoke_atris
from atris_tools.phantom_calibration import (
    PhantomEvents,
    PhantomStatistics,
    prepare_water_phantom,
    read_phantom_statistics,
)

EVENTS = 64


def prepare_calibration(directory, particle, *, miss=False, events=EVENTS):
    directory.mkdir()
    radius = 4e-4
    prepare_water_phantom(directory, [0.001, 10], radius_cm=radius, particle=particle,
                          events_per_chunk=events, production_cut_mm=0.00001,
                          tracking_floor_eV=1)
    macro = directory / "calibration.chunk.mac"
    macro.write_text(macro.read_text().replace("/run/beamOn",
        "/gps/pos/type Point\n"
        f"/gps/pos/centre {1.5 * radius if miss else 0} 0 {-1.1 * radius} cm\n"
        "/run/beamOn"))
    (directory / "calibration.mac").symlink_to(macro.name)


@pytest.mark.regression
@pytest.mark.parametrize("particle", ("proton", "e-", "gamma", "neutron", "alpha"))
@pytest.mark.parametrize("threads", ("1", "2"))
def test_phantom_matches_shower_and_retains_per_bin_statistics(
    tmp_path, atris_command, particle, threads
):
    outputs = {}
    sizes = {}
    for mode in ("1", "phantom"):
        directory = tmp_path / mode
        prepare_calibration(directory, particle)
        result = invoke_atris(
            atris_command,
            directory,
            "FTFP_BERT_HP",
            "calibration_123456_654321.root",
            mode,
            "0",
            threads=threads,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        if mode == "phantom":
            assert "Processing event:" not in result.stdout
        path = directory / "calibration_123456_654321.root"
        sizes[mode] = path.stat().st_size
        with uproot.open(path) as root:
            if mode == "1":
                steps = root["steps"].arrays(library="np")
                ids = steps["event_id"]
                water = steps["detector_id"] == 1
                incident = np.zeros(EVENTS)
                np.maximum.at(incident, ids, steps["primary_energy_MeV"])
                deposited = np.bincount(
                    ids[water],
                    weights=steps["energy_deposit_MeV"][water],
                    minlength=EVENTS,
                )
                ionizing = np.bincount(
                    ids[water],
                    weights=(
                        steps["energy_deposit_MeV"]
                        - steps["nonionizing_energy_deposit_MeV"]
                    )[water],
                    minlength=EVENTS,
                )
                outputs[mode] = PhantomStatistics.from_events(
                    PhantomEvents(incident, deposited, ionizing)
                )
            else:
                assert not {"steps", "interfaces", "phantom_events"} & set(
                    root.keys(cycle=False)
                )
                assert root["metadata"]["output_mode"].array(library="np").tolist() == [
                    3
                ]
                assert len(root["h2.fraction"].member("fSumw2")) > 0
                outputs[mode] = read_phantom_statistics(path)
                stats = outputs[mode]
                assert stats.sample_counts.sum() == EVENTS
                assert np.all(stats.detected_counts <= stats.sample_counts)
                assert np.all(stats.squared_deviations >= 0)
    # Repeated shower-only MT runs also differ in their event streams. Compare
    # exact transport histories serially; above checks cover merged MT scoring.
    if threads == "1":
        for field in PhantomStatistics.__dataclass_fields__:
            np.testing.assert_allclose(
                getattr(outputs["phantom"], field),
                getattr(outputs["1"], field),
                rtol=1e-12,
                atol=1e-14,
            )
    assert sizes["phantom"] < sizes["1"]


@pytest.mark.regression
def test_phantom_counts_primaries_that_never_enter_water(tmp_path, atris_command):
    directory = tmp_path / "miss"
    prepare_calibration(directory, "proton", miss=True)
    result = invoke_atris(
        atris_command,
        directory,
        "FTFP_BERT_HP",
        "calibration",
        "phantom",
        "0",
        threads="2",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    stats = read_phantom_statistics(directory / "calibration.root")
    assert stats.sample_counts.sum() == EVENTS
    assert not np.any(stats.mean_fraction)
    assert not np.any(stats.squared_deviations)
    assert not np.any(stats.detected_counts)
    with pytest.raises(ValueError, match="zero counting threshold"):
        read_phantom_statistics(directory / "calibration.root", threshold_MeV=0.001)
    with uproot.open(directory / "calibration.root") as root:
        assert root["h1.1"].member("fEntries") == EVENTS


@pytest.mark.regression
def test_phantom_output_does_not_store_records_per_primary(tmp_path, atris_command):
    sizes = []
    for events in (64, 65000):
        directory = tmp_path / str(events)
        prepare_calibration(directory, "proton", events=events)
        result = invoke_atris(
            atris_command,
            directory,
            "FTFP_BERT_HP",
            "calibration",
            "phantom",
            "0",
            threads="2",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        path = directory / "calibration.root"
        stats = read_phantom_statistics(path)
        assert stats.sample_counts.sum() == events
        assert stats.sample_counts.shape == (650,)
        with uproot.open(path) as root:
            trees = {
                name
                for name, cls in root.classnames(cycle=False).items()
                if cls == "TTree"
            }
            assert trees == {"metadata"}
        sizes.append(path.stat().st_size)
    # Compression changes with occupied bins, but not one record per primary.
    assert sizes[1] < 3 * sizes[0]
