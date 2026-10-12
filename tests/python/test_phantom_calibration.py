import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import uproot

from atris_tools.phantom_calibration import (
    PhantomEvents,
    PhantomResponse,
    PhantomStatistics,
    RESPONSE_ENERGY_EDGES_MEV,
    calibrate_water_phantom,
    compact_water_phantom_chunk,
    prepare_water_phantom,
    read_phantom_statistics,
    read_water_phantom_events,
)
from atris_tools.phantoms import read_phantoms, stage_phantoms
from atris_tools.phantom_tables import PhantomTable


def test_geometry_keeps_source_and_water_inside_termination_shells(tmp_path):
    prepare_water_phantom(tmp_path, [1, 10, 100], radius_cm=4, chunks=2)
    gdml = ET.parse(tmp_path / "calibration.gdml")
    spheres = {s.attrib["name"]: s.attrib for s in gdml.findall("./solids/sphere")}
    assert float(spheres["solid1"]["rmax"]) == pytest.approx(4 / 1e5)
    # The whole incident disk at z = -1.1 R is inside the escape shell.
    assert np.hypot(4, 1.1 * 4) / 1e5 < float(spheres["solid0"]["rmin"])
    volumes = {v.attrib["name"]: v for v in gdml.findall("./structure/volume")}
    assert volumes["volume1"].find("auxiliary").attrib["auxvalue"] == "1"
    assert len(gdml.findall(".//auxiliary")) == 3
    assert len((tmp_path / "chunks.txt").read_text().splitlines()) == 2
    np.testing.assert_array_equal(
        np.loadtxt(tmp_path / "calibration.bins"), RESPONSE_ENERGY_EDGES_MEV
    )


def test_repreparing_same_setup_preserves_results_but_changed_setup_is_rejected(
    tmp_path,
):
    prepare_water_phantom(tmp_path, [1, 10])
    result = tmp_path / "chunks" / "existing.root"
    result.write_bytes(b"results")
    original = (tmp_path / "calibration.gdml").read_text()
    prepare_water_phantom(tmp_path, [1, 10])
    with pytest.raises(FileExistsError):
        prepare_water_phantom(tmp_path, [1, 10], radius_cm=5)
    assert result.read_bytes() == b"results"
    assert (tmp_path / "calibration.gdml").read_text() == original


def test_event_sums_include_secondaries_zero_deposits_and_local_chunk_ids(tmp_path):
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks.txt").write_text(
        "calibration 111111 222222\ncalibration 333333 444444\n"
    )
    for a, b in [(111111, 222222), (333333, 444444)]:
        name = f"calibration_{a}_{b}"
        with uproot.recreate(tmp_path / "chunks" / (name + ".root")) as root:
            root.mktree(
                "metadata",
                {"atris_version": ["trial"], "physics_list": ["FTFP_BERT_HP"]},
            )
            root["h1.1"] = np.histogram([10, 10, 10], bins=[1, 100])
            # Unsorted steps: event 0 includes two water deposits, event 1
            # deposits zero, and event 2 also deposits energy outside water.
            root["steps"] = {
                "event_id": np.array([2, 0, 1, 0, 2]),
                "detector_id": np.array([0, 1, 1, 1, 1]),
                "primary_energy_MeV": np.full(5, 10.0),
                "energy_deposit_MeV": np.array([99.0, 3.0, 0.0, 2.0, 4.0]),
                "nonionizing_energy_deposit_MeV": np.array([0.0, 0.2, 0.0, 0.3, 1.0]),
            }
        (tmp_path / "chunks" / (name + ".COMPLETE")).touch()
    events = read_water_phantom_events(tmp_path)
    np.testing.assert_array_equal(events.incident_energy_MeV, np.full(6, 10.0))
    np.testing.assert_array_equal(events.deposited_energy_MeV, [5, 0, 4, 5, 0, 4])
    np.testing.assert_allclose(events.ionizing_energy_MeV, [4.5, 0, 3, 4.5, 0, 3])
    for path in (tmp_path / "chunks").glob("*.root"):
        compact_water_phantom_chunk(path)
        compact_water_phantom_chunk(path)
        with uproot.open(path) as root:
            assert "steps" not in root
            assert "phantom_events" in root
            assert root["h1.1"].member("fEntries") == 3
            assert root["metadata"]["atris_version"].array(library="np").tolist() == [
                "trial"
            ]
    compacted = read_water_phantom_events(tmp_path)
    for name in events.__dataclass_fields__:
        np.testing.assert_array_equal(getattr(compacted, name), getattr(events, name))


def test_incomplete_chunks_are_not_read(tmp_path):
    prepare_water_phantom(tmp_path, [1, 10])
    with pytest.raises(ValueError, match="No completed"):
        read_water_phantom_events(tmp_path)


def test_native_phantom_mode_selects_water_and_keeps_zero_events(tmp_path):
    prepare_water_phantom(tmp_path, [1, 100], chunks=1)
    entry = (tmp_path / "chunks.txt").read_text().split()
    name = "_".join(entry)
    with uproot.recreate(tmp_path / "chunks" / (name + ".root")) as root:
        root.mktree(
            "phantom_events",
            {
                "event_id": np.array([0, 0, 1, 1]),
                "detector_id": np.array([1, 2, 1, 2]),
                "incident_energy_MeV": np.array([10.0, 10.0, 20.0, 20.0]),
                "deposited_energy_MeV": np.array([5.0, 99.0, 0.0, 99.0]),
                "ionizing_energy_MeV": np.array([4.0, 90.0, 0.0, 90.0]),
            },
        )
    (tmp_path / "chunks" / (name + ".COMPLETE")).touch()
    events = read_water_phantom_events(tmp_path)
    np.testing.assert_array_equal(events.incident_energy_MeV, [10, 20])
    np.testing.assert_array_equal(events.deposited_energy_MeV, [5, 0])
    np.testing.assert_array_equal(events.ionizing_energy_MeV, [4, 0])
    statistics = read_phantom_statistics(tmp_path / "chunks" / (name + ".root"))
    expected = PhantomStatistics.from_events(events)
    for field in PhantomStatistics.__dataclass_fields__:
        np.testing.assert_array_equal(
            getattr(statistics, field), getattr(expected, field)
        )
    np.testing.assert_array_equal(
        read_phantom_statistics(
            tmp_path / "chunks" / (name + ".root"), threshold_MeV=4
        ).detected_counts,
        0,
    )


@pytest.mark.parametrize("edges", [[0, 1], [1, 1], [1, np.nan], [1, np.inf]])
def test_invalid_energy_edges_are_rejected_before_writing(tmp_path, edges):
    with pytest.raises(ValueError):
        prepare_water_phantom(tmp_path, edges)
    assert not (tmp_path / "chunks.txt").exists()


def test_increasing_chunk_count_appends_without_changing_existing_jobs(tmp_path):
    prepare_water_phantom(tmp_path, [1, 10], chunks=2)
    original = (tmp_path / "chunks.txt").read_text()
    macro = (tmp_path / "calibration.chunk.mac").read_text()
    prepare_water_phantom(tmp_path, [1, 10], chunks=4)
    expanded = (tmp_path / "chunks.txt").read_text()
    assert expanded.startswith(original)
    assert len(set(expanded.splitlines())) == 4
    assert (tmp_path / "calibration.chunk.mac").read_text() == macro
    prepare_water_phantom(tmp_path, [1, 10], chunks=2)
    assert (tmp_path / "chunks.txt").read_text() == expanded


def test_ion_source_sets_isotope_charge_and_ground_state(tmp_path):
    ion = {"Z": 6, "A": 12, "charge": 6}
    prepare_water_phantom(tmp_path, [12, 120], particle="ion", ion=ion)
    macro = (tmp_path / "calibration.chunk.mac").read_text()
    assert "/gps/particle ion\n/gps/ion 6 12 6 0\n" in macro
    assert f"/gps/ene/min {12.0:.17e} MeV" in macro
    assert json.loads((tmp_path / "water-phantom.json").read_text())["ion"] == ion
    prepare_water_phantom(tmp_path, [12, 120], particle="ion", ion=ion)
    with pytest.raises(FileExistsError):
        prepare_water_phantom(
            tmp_path, [12, 120], particle="ion", ion={"Z": 6, "A": 13, "charge": 6}
        )


@pytest.mark.parametrize(
    "particle,ion",
    [
        ("ion", None),
        ("proton", {"Z": 6, "A": 12, "charge": 6}),
        ("ion", {"Z": 6, "A": 4, "charge": 6}),
        ("ion", {"Z": 6, "A": 12, "charge": 7}),
    ],
)
def test_invalid_ion_setup_is_rejected_before_writing(tmp_path, particle, ion):
    with pytest.raises(ValueError):
        prepare_water_phantom(tmp_path, [1, 10], particle=particle, ion=ion)
    assert not (tmp_path / "chunks.txt").exists()


@pytest.fixture
def calibration(tmp_path, monkeypatch):
    import atris_tools.phantom_calibration as module

    centres = np.sqrt(RESPONSE_ENERGY_EDGES_MEV[:-1] * RESPONSE_ENERGY_EDGES_MEV[1:])
    # Two events per bin. One leaves no energy; the other leaves all of it.
    incident = np.repeat(centres, 2)
    deposited = incident * np.tile([0.0, 1.0], len(centres))
    events = PhantomEvents(incident, deposited, deposited)
    monkeypatch.setattr(
        module,
        "read_phantom_statistics",
        lambda *args: PhantomStatistics.from_events(events),
    )
    monkeypatch.setattr(
        module,
        "read_ntuple",
        lambda *args: np.empty(
            0, dtype=[("atris_version", "U1"), ("physics_list", "U1")]
        ),
    )
    config = {"radius_cm": 15.0, "density_g_cm3": 0.997, "production_cut_mm": 0.1}
    (tmp_path / "water-phantom.json").write_text(json.dumps(config))
    (tmp_path / "chunks.txt").write_text("calibration 111111 222222\n")
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks/calibration_111111_222222.COMPLETE").touch()
    return calibrate_water_phantom({22: tmp_path, 2212: tmp_path})


def test_export_preserves_zero_events_statistics_units_and_selection(
    calibration, tmp_path
):
    np.testing.assert_allclose(calibration.energy_fraction, 0.5)
    np.testing.assert_allclose(calibration.counting_efficiency, 0.5)
    np.testing.assert_array_equal(calibration.sample_counts, 2)
    np.testing.assert_allclose(calibration.fraction_standard_error, 0.5)
    np.testing.assert_allclose(calibration.fraction_variance, 0.5)
    np.testing.assert_allclose(calibration.counting_variance, 0.5)
    np.testing.assert_allclose(calibration.counting_standard_error, 0.5)
    calibration.write(tmp_path, fmt="%.8e")
    for suffix in ["response", "counting"]:
        p = tmp_path / f"water-sphere_{suffix}.txt"
        table = PhantomTable.read(p, counting=suffix == "counting")
        np.testing.assert_array_equal(table.pdg_codes, [22, 2212])
        assert table.coefficients.shape == (2, 650)
        np.testing.assert_allclose(table.coefficients, 0.5)
        assert table.metadata["radius_cm"] == "15.0"
        assert table.metadata["production_cut_mm"] == "0.1"
        assert table.metadata["physics_list"] == "not recorded"
        assert table.metadata["counting_threshold_MeV"] == "0.0"
        assert "zero-deposit events included" in table.metadata["normalization"]
        assert "standard error" in table.metadata["uncertainty"]
    variance = np.loadtxt(tmp_path / "water-sphere_variance.txt", skiprows=8)
    assert variance.shape == (2, 650)
    np.testing.assert_allclose(variance, 0.5)
    with np.load(tmp_path / "water-sphere_sampling.npz") as statistics:
        np.testing.assert_array_equal(statistics["sample_counts"], 2)
        np.testing.assert_array_equal(statistics["detected_counts"], 1)
        np.testing.assert_allclose(statistics["fraction_variance"], 0.5)
        np.testing.assert_allclose(statistics["fraction_standard_error"], 0.5)
        np.testing.assert_allclose(statistics["counting_variance"], 0.5)
        np.testing.assert_allclose(statistics["counting_standard_error"], 0.5)
    metadata = json.loads((tmp_path / "water-sphere_calibration.json").read_text())
    assert metadata["physics_list"] == "not recorded"
    assert "N-1" in metadata["variance_definition"]
    metadata = read_phantoms(tmp_path)[0]
    assert metadata["area"] == pytest.approx(2 * np.pi * 15**2)
    assert metadata["mass"] == pytest.approx(4 / 3 * np.pi * 15**3 * 0.997)
    stage_phantoms(tmp_path)
    assert (
        tmp_path / "radiation_phantom0.txt"
    ).resolve() == tmp_path / "water-sphere_response.txt"


def test_export_rejects_unsampled_bins_without_creating_files(calibration, tmp_path):
    calibration.sample_counts[1, 0] = 0
    with pytest.raises(ValueError, match="Unsampled"):
        calibration.write(tmp_path / "export")
    assert not (tmp_path / "export").exists()


def test_live_export_marks_unsampled_bins_without_inventing_zeros(
    calibration, tmp_path
):
    calibration.sample_counts[1, 0] = 0
    calibration.energy_fraction[1, 0] = np.nan
    calibration.counting_efficiency[1, 0] = np.nan
    calibration.fraction_standard_error[1, 0] = np.nan
    calibration.write(tmp_path, allow_partial=True)
    path = tmp_path / "water-sphere_response.txt"
    with pytest.raises(ValueError, match="finite"):
        PhantomTable.read(path)
    table = PhantomTable.read(path, allow_missing=True)
    assert np.isnan(table.coefficients[1, 0])
    assert "not yet loadable" in table.metadata["sampling_status"]
    with np.load(tmp_path / "water-sphere_sampling.npz") as statistics:
        assert statistics["sample_counts"][1, 0] == 0
        assert statistics["detected_counts"][1, 0] == 0
        assert np.isnan(statistics["fraction_variance"][1, 0])


def test_export_requires_photons_first(calibration, tmp_path):
    calibration.pdg_codes = np.array([2212, 22])
    with pytest.raises(ValueError, match="photons"):
        calibration.write(tmp_path / "export")


def test_one_sample_has_no_estimated_variance(calibration):
    calibration.sample_counts[:, 0] = 1
    calibration.fraction_standard_error[:, 0] = np.nan
    assert np.all(np.isnan(calibration.fraction_variance[:, 0]))
    assert np.all(np.isnan(calibration.counting_variance[:, 0]))
    assert np.all(np.isnan(calibration.counting_standard_error[:, 0]))


def test_incremental_statistics_match_all_events_including_zero_deposits():
    centres = np.sqrt(RESPONSE_ENERGY_EDGES_MEV[:-1] * RESPONSE_ENERGY_EDGES_MEV[1:])
    incident = np.repeat(centres, 4)
    deposited = incident * np.tile([0.0, 0.25, 0.5, 1.0], len(centres))
    events = PhantomEvents(incident, deposited, deposited)
    incremental = PhantomStatistics.empty()
    for start, end in ((0, 17), (17, 593), (593, len(incident))):
        incremental += PhantomStatistics.from_events(
            PhantomEvents(
                *(
                    getattr(events, name)[start:end]
                    for name in events.__dataclass_fields__
                )
            )
        )
    together = PhantomStatistics.from_events(events)
    for name in together.__dataclass_fields__:
        np.testing.assert_allclose(
            getattr(incremental, name), getattr(together, name), atol=1e-14
        )
    response = PhantomResponse.from_statistics(
        {22: incremental}, radius_cm=4e-4, density_g_cm3=0.997
    )
    np.testing.assert_array_equal(response.sample_counts, 4)
    np.testing.assert_allclose(response.counting_efficiency, 0.75)
    np.testing.assert_allclose(
        response.fraction_variance, np.var([0, 0.25, 0.5, 1], ddof=1)
    )
