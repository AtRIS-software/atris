"""Compare compact calibration scoring with the existing shower records."""

from pathlib import Path

import numpy as np
import pytest
import uproot

from test_atris_command import atris_command, invoke_atris

ROOT = Path(__file__).resolve().parents[2]
EDGES = np.geomspace(1e-6, 1e7, 651)
EVENTS = 64


def prepare_calibration(directory, particle, *, miss=False):
    directory.mkdir()
    template = (ROOT / "atris_tools/data/water-phantom.gdml").read_text()
    radius = 4e-4
    (directory / "calibration.gdml").write_text(
        template.format(
            radius=radius,
            density=0.997,
            world_size=8 * radius,
            escape_inner=2 * radius,
            escape_outer=2.1 * radius,
            guard_inner=2.2 * radius,
            guard_outer=2.3 * radius,
        )
    )
    np.savetxt(directory / "calibration.bins", EDGES)
    (directory / "calibration.mac").write_text(
        "/process/em/lowestElectronEnergy 1 eV\n"
        "/process/em/lowestMuHadEnergy 1 eV\n"
        "/run/setCut 0.00001 mm\n"
        "/run/initialize\n"
        f"/gps/particle {particle}\n"
        "/gps/pos/type Point\n"
        f"/gps/pos/centre {1.5 * radius if miss else 0} 0 {-1.1 * radius} cm\n"
        "/gps/direction 0 0 1\n"
        "/gps/ene/type Pow\n"
        "/gps/ene/alpha -1\n"
        "/gps/ene/min 0.001 MeV\n"
        "/gps/ene/max 10 MeV\n"
        f"/run/beamOn {EVENTS}\n"
    )


@pytest.mark.regression
@pytest.mark.parametrize("particle", ("proton", "e-", "gamma", "neutron", "alpha"))
@pytest.mark.parametrize("threads", ("1", "2"))
def test_phantom_matches_shower_and_retains_event_statistics(
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
                outputs[mode] = (incident, deposited, ionizing)
            else:
                assert "steps" not in root and "interfaces" not in root
                assert root["metadata"]["output_mode"].array(library="np").tolist() == [
                    3
                ]
                events = root["phantom_events"].arrays(library="np")
                order = np.argsort(events["event_id"])
                np.testing.assert_array_equal(
                    events["event_id"][order], np.arange(EVENTS)
                )
                np.testing.assert_array_equal(events["detector_id"], 1)
                outputs[mode] = tuple(
                    events[name][order]
                    for name in (
                        "incident_energy_MeV",
                        "deposited_energy_MeV",
                        "ionizing_energy_MeV",
                    )
                )
                incident, deposited, ionizing = outputs[mode]
                fraction = ionizing / incident
                # ROOT flow bins bracket the 650 interior energy bins.
                np.testing.assert_array_equal(
                    root["h1.1"].values(),
                    np.histogram(incident, EDGES)[0],
                )
                for name, weights in (("h2.edep", deposited), ("h2.ion", ionizing)):
                    np.testing.assert_allclose(
                        root[name].values(flow=True)[1:-1, 2],
                        np.histogram(incident, EDGES, weights=weights)[0],
                        rtol=1e-12,
                        atol=1e-14,
                    )
                np.testing.assert_allclose(
                    root["h2.fraction"].values(flow=True)[1:-1, 2],
                    np.histogram(incident, EDGES, weights=fraction)[0],
                    rtol=1e-12,
                    atol=1e-14,
                )
                np.testing.assert_allclose(
                    root["h2.fraction"].variances(flow=True)[1:-1, 2],
                    np.histogram(incident, EDGES, weights=fraction**2)[0],
                    rtol=1e-12,
                    atol=1e-14,
                )
                np.testing.assert_array_equal(
                    root["h2.detected"].values(flow=True)[1:-1, 2],
                    np.histogram(incident[ionizing > 0], EDGES)[0],
                )
    # Repeated shower-only MT runs also differ in their event streams. Compare
    # exact transport histories serially; above checks cover merged MT scoring.
    if threads == "1":
        for shower, phantom in zip(outputs["1"], outputs["phantom"]):
            np.testing.assert_allclose(phantom, shower, rtol=1e-12, atol=1e-14)
    assert sizes["phantom"] < sizes["1"]


@pytest.mark.regression
def test_phantom_keeps_events_that_never_enter_water(tmp_path, atris_command):
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
    with uproot.open(directory / "calibration.root") as root:
        events = root["phantom_events"].arrays(library="np")
        assert len(events["event_id"]) == EVENTS
        assert np.all(events["incident_energy_MeV"] > 0)
        assert not np.any(events["deposited_energy_MeV"])
        assert not np.any(events["ionizing_energy_MeV"])
        assert root["h1.1"].member("fEntries") == EVENTS
