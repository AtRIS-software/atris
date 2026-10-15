"""Tests for phantom-response data and file handling."""

import json
from dataclasses import asdict, replace
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import uproot

from atris_tools.phantom import (
    PhantomEvents,
    Phantom,
    PhantomStatistics,
    RESPONSE_ENERGY_EDGES_MEV,
    compact_phantom_chunk,
    prepare_phantom_batch,
    read_phantom_statistics,
    gather_phantom_events,
)
from atris_tools.phantoms import read_phantoms, stage_phantoms
from atris_tools.phantom_tables import PhantomTable
from atris_tools.psf import PSF


def water_psf(radius_cm=15):
    return PSF(inner_radius_km=0, outer_radius_km=radius_cm / 1e5,
               temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
               mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
               state="liquid")


@pytest.mark.parametrize("energies,counts", [([], (0, 0, 0, 0)), ([1, 1, 10], (3, 2, 1, 1))])
def test_event_and_statistics_summaries_retain_field_based_repr(energies, counts):
    incident = np.array(energies, dtype=float)
    deposit = np.zeros_like(incident)
    deposit[1:2] = .5
    events = PhantomEvents(incident, deposit, deposit)
    statistics = PhantomStatistics.from_events(events)
    primaries, sampled, repeated, detected = counts
    assert f"Phantom events: {primaries} primaries" in str(events)
    assert f"Positive ionizing deposits: {detected}" in str(events)
    if primaries:
        assert "Incident kinetic energy: 1 to 10 MeV" in str(events)
    else:
        assert "Incident kinetic energy:" not in str(events)
    summary = str(statistics)
    assert f"Primaries: {primaries}" in summary
    assert f"Sampled energy bins: {sampled}/650" in summary
    assert f"Bins with at least two primaries: {repeated}" in summary
    assert f"Counted primaries: {detected}" in summary
    assert "array(" not in summary
    assert repr(events).startswith("PhantomEvents(incident_energy_MeV=array(")
    assert repr(statistics).startswith("PhantomStatistics(sample_counts=array(")


def test_geometry_keeps_source_and_water_inside_termination_shells(tmp_path):
    prepare_phantom_batch(tmp_path, [1, 10, 100], psf_path=water_psf(4), chunks=2)
    gdml = ET.parse(tmp_path / "phantom.gdml")
    spheres = {s.attrib["name"]: s.attrib for s in gdml.findall("./solids/sphere")}
    assert float(spheres["solid1"]["rmax"]) == pytest.approx(4 / 1e5)
    # The whole incident disk at z = -1.1 R is inside the escape shell.
    assert np.hypot(4, 1.1 * 4) / 1e5 < float(spheres["solid0"]["rmin"])
    volumes = {v.attrib["name"]: v for v in gdml.findall("./structure/volume")}
    assert volumes["volume1"].find("auxiliary").attrib["auxvalue"] == "1"
    assert len(gdml.findall(".//auxiliary")) == 3
    assert len((tmp_path / "chunks.txt").read_text().splitlines()) == 2
    np.testing.assert_array_equal(
        np.loadtxt(tmp_path / "phantom.bins"), RESPONSE_ENERGY_EDGES_MEV
    )


def test_repreparing_same_setup_preserves_results_but_changed_setup_is_rejected(
    tmp_path,
):
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf())
    result = tmp_path / "chunks" / "existing.root"
    result.write_bytes(b"results")
    original = (tmp_path / "phantom.gdml").read_text()
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf())
    with pytest.raises(FileExistsError):
        prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf(5))
    assert result.read_bytes() == b"results"
    assert (tmp_path / "phantom.gdml").read_text() == original


def test_prepare_uses_psf_material_settings_without_json_geometry(tmp_path):
    from atris_tools.psf import (
        DETECTOR_ID, TEMPERATURE, PSF, load_psf, write_psf,
    )
    sphere = PSF(inner_radius_km=[0], outer_radius_km=[4e-9],
        temperature_k=301, density_g_cm3=.99, pressure_pa=90000,
        mass_fractions={"O": 15.9994 / 18.01528, "H": 2 * 1.00794 / 18.01528},
        solid_composition="H112O888", state="liquid")
    source = tmp_path / "water.psf"
    write_psf(source, sphere)
    run = tmp_path / "run"
    run.mkdir()
    prepare_phantom_batch(run, [1, 10], psf_path=source)
    expected = sphere.layers.copy()
    expected[:, DETECTOR_ID] = 1
    np.testing.assert_array_equal(load_psf(run / "phantom.psf")[:1], expected)
    config = json.loads((run / "phantom-run.json").read_text())
    assert "radius_cm" not in config
    assert "density_g_cm3" not in config
    prepare_phantom_batch(run, [1, 10], psf_path=source)
    changed = sphere.layers.copy()
    changed[:, TEMPERATURE] += 1
    write_psf(source, PSF.from_layers(changed, sphere.materials))
    with pytest.raises(FileExistsError):
        prepare_phantom_batch(run, [1, 10], psf_path=source)


def test_event_sums_include_secondaries_zero_deposits_and_local_chunk_ids(tmp_path):
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks.txt").write_text(
        "phantom 111111 222222\nphantom 333333 444444\n"
    )
    for a, b in [(111111, 222222), (333333, 444444)]:
        name = f"phantom_{a}_{b}"
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
    events = gather_phantom_events(tmp_path)
    np.testing.assert_array_equal(events.incident_energy_MeV, np.full(6, 10.0))
    np.testing.assert_array_equal(events.deposited_energy_MeV, [5, 0, 4, 5, 0, 4])
    np.testing.assert_allclose(events.ionizing_energy_MeV, [4.5, 0, 3, 4.5, 0, 3])
    for path in (tmp_path / "chunks").glob("*.root"):
        compact_phantom_chunk(path)
        compact_phantom_chunk(path)
        with uproot.open(path) as root:
            assert "steps" not in root
            assert "phantom_events" in root
            assert root["h1.1"].member("fEntries") == 3
            assert root["metadata"]["atris_version"].array(library="np").tolist() == [
                "trial"
            ]
    compacted = gather_phantom_events(tmp_path)
    for name in events.__dataclass_fields__:
        np.testing.assert_array_equal(getattr(compacted, name), getattr(events, name))


def test_incomplete_chunks_are_not_read(tmp_path):
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf())
    with pytest.raises(ValueError, match="No completed"):
        gather_phantom_events(tmp_path)


def test_native_phantom_mode_selects_water_and_keeps_zero_events(tmp_path):
    prepare_phantom_batch(tmp_path, [1, 100], psf_path=water_psf(), chunks=1)
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
    events = gather_phantom_events(tmp_path)
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
        prepare_phantom_batch(tmp_path, edges, psf_path=water_psf())
    assert not (tmp_path / "chunks.txt").exists()


def test_increasing_chunk_count_appends_without_changing_existing_jobs(tmp_path):
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf(), chunks=2)
    original = (tmp_path / "chunks.txt").read_text()
    macro = (tmp_path / "phantom.chunk.mac").read_text()
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf(), chunks=4)
    expanded = (tmp_path / "chunks.txt").read_text()
    assert expanded.startswith(original)
    assert len(set(expanded.splitlines())) == 4
    assert (tmp_path / "phantom.chunk.mac").read_text() == macro
    prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf(), chunks=2)
    assert (tmp_path / "chunks.txt").read_text() == expanded


def test_ion_source_sets_isotope_charge_and_ground_state(tmp_path):
    ion = {"Z": 6, "A": 12, "charge": 6}
    prepare_phantom_batch(tmp_path, [12, 120], psf_path=water_psf(), particle="ion", ion=ion)
    macro = (tmp_path / "phantom.chunk.mac").read_text()
    assert "/gps/particle ion\n/gps/ion 6 12 6 0\n" in macro
    assert f"/gps/ene/min {12.0:.17e} MeV" in macro
    assert json.loads((tmp_path / "phantom-run.json").read_text())["ion"] == ion
    prepare_phantom_batch(tmp_path, [12, 120], psf_path=water_psf(), particle="ion", ion=ion)
    with pytest.raises(FileExistsError):
        prepare_phantom_batch(
            tmp_path, [12, 120], psf_path=water_psf(), particle="ion", ion={"Z": 6, "A": 13, "charge": 6}
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
        prepare_phantom_batch(tmp_path, [1, 10], psf_path=water_psf(), particle=particle, ion=ion)
    assert not (tmp_path / "chunks.txt").exists()


@pytest.fixture
def phantom(tmp_path, monkeypatch):
    import atris_tools.phantom as module

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
        lambda *args: np.array(
            [("test", "FTFP_BERT_HP")],
            dtype=[("atris_version", "U4"), ("physics_list", "U12")]),
    )
    from atris_tools.psf import DETECTOR_ID, PSF, write_psf
    sphere = PSF(inner_radius_km=[0], outer_radius_km=[15 / 1e5],
        temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
        mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
        solid_composition="H112O888", state="liquid")
    sphere.layers[:, DETECTOR_ID] = 1
    from atris_tools.phantom_builder import PhantomBuilder
    builder = PhantomBuilder(sphere, [22, 2212], directory=tmp_path, name="water-sphere")
    records = []
    for index, code in enumerate((22, 2212)):
        directory = tmp_path / "batches" / f"batch-{index:06d}"
        directory.mkdir(parents=True)
        (directory / "chunks.txt").write_text(f"phantom {111111 + index} {222222 + index}\n")
        (directory / "chunks").mkdir()
        (directory / "chunks" / f"phantom_{111111 + index}_{222222 + index}.COMPLETE").touch()
        records.append(dict(pdg=code, directory=str(directory.relative_to(tmp_path))))
    (tmp_path / "batches.json").write_text(json.dumps(records))
    return Phantom.gather("water-sphere", directory=builder.directory)


def test_export_preserves_zero_events_statistics_units_and_explicit_selection(
    phantom, tmp_path
):
    np.testing.assert_allclose(phantom.energy_fraction, 0.5)
    np.testing.assert_allclose(phantom.counting_efficiency, 0.5)
    np.testing.assert_array_equal(phantom.sample_counts, 2)
    np.testing.assert_allclose(phantom.fraction_standard_error, 0.5)
    np.testing.assert_allclose(phantom.fraction_variance, 0.5)
    np.testing.assert_allclose(phantom.counting_variance, 0.5)
    np.testing.assert_allclose(phantom.counting_standard_error, 0.5)
    phantom.save(tmp_path, fmt="%.8e")
    for suffix in ["response", "counting"]:
        p = tmp_path / f"water-sphere_{suffix}.txt"
        table = PhantomTable.read(p, counting=suffix == "counting")
        np.testing.assert_array_equal(table.pdg_codes, [22, 2212])
        assert table.coefficients.shape == (2, 650)
        np.testing.assert_allclose(table.coefficients, 0.5)
        assert float(table.metadata["radius_cm"]) == pytest.approx(15.0)
        assert table.metadata["counting_threshold_MeV"] == "0.0"
        assert table.metadata["sampling_file"] == "water-sphere_sampling.root"
        assert "production_cut_mm" not in table.metadata
    assert not (tmp_path / "water-sphere_variance.txt").exists()
    import uproot
    with uproot.open(tmp_path / "water-sphere_sampling.root") as root:
        statistics = root["sampling"].arrays(library="np")
        np.testing.assert_array_equal(statistics["sample_counts"], 2)
        np.testing.assert_array_equal(statistics["detected_counts"], 1)
        np.testing.assert_allclose(statistics["fraction_variance"], 0.5)
        np.testing.assert_allclose(statistics["fraction_standard_error"], 0.5)
        np.testing.assert_allclose(statistics["counting_variance"], 0.5)
        np.testing.assert_allclose(statistics["counting_standard_error"], 0.5)
    retained = Phantom.read_root(tmp_path / "water-sphere_sampling.root")
    metadata = retained.metadata
    assert "H112O888" in retained.geometry.materials
    with uproot.open(tmp_path / "water-sphere_sampling.root") as root:
        exported = json.loads(str(root["metadata"]))
    assert exported["validity"]["scoring_detector_ids"] == [1]
    assert exported["validity"]["termination_detector_ids"] == [0, 2]
    assert not (tmp_path / "water-sphere_phantom.json").exists()
    assert metadata["physics_list"] == "FTFP_BERT_HP"
    assert exported["variance_ddof"] == 1
    assert "radius_cm" not in metadata
    assert "precision_settings" not in metadata
    assert not (tmp_path / "phantoms.txt").exists()
    (tmp_path / "phantoms.txt").write_text(
        f"0 water-sphere {phantom.mass_g:.17e} {phantom.area_cm2:.17e}\n")
    metadata = read_phantoms(tmp_path)[0]
    assert metadata["area"] == pytest.approx(2 * np.pi * 15**2)
    assert metadata["mass"] == pytest.approx(4 / 3 * np.pi * 15**3 * 0.997)
    stage_phantoms(tmp_path)
    assert (
        tmp_path / "radiation_phantom0.txt"
    ).resolve() == tmp_path / "water-sphere_response.txt"


def test_export_rejects_unsampled_bins_without_creating_files(phantom, tmp_path):
    phantom.sample_counts[1, 0] = 0
    with pytest.raises(ValueError, match="Unsampled"):
        phantom.save(tmp_path / "export", allow_partial=False)
    assert not (tmp_path / "export").exists()


@pytest.mark.parametrize("existing_selection", [False, True])
@pytest.mark.parametrize("with_precision", [False, True])
def test_save_preserves_selection_and_returns_only_written_paths(
    phantom, tmp_path, existing_selection, with_precision
):
    selection = tmp_path / "phantoms.txt"
    original = b"# Keep both selected phantoms.\n0 first 1 2\n1 second 3 4\n"
    if existing_selection:
        selection.write_bytes(original)
    if not with_precision:
        phantom.precision_settings = None
    paths = phantom.save(tmp_path)
    suffixes = ("response.txt", "counting.txt", "sampling.root")
    if with_precision:
        suffixes += ("sampling-state.json",)
    assert paths == tuple(tmp_path / f"water-sphere_{suffix}" for suffix in suffixes)
    assert all(path.is_file() for path in paths)
    other_paths = phantom.save(tmp_path, name="another")
    assert all(path.is_file() for path in paths + other_paths)
    if existing_selection:
        assert selection.read_bytes() == original
    else:
        assert not selection.exists()


def test_sampling_root_round_trip_preserves_arrays_and_metadata(phantom, tmp_path):
    phantom.metadata["example_provenance"] = {"runs": ["pilot", "refinement"]}
    phantom.sample_counts[1, 0] = 0
    phantom.energy_fraction[1, 0] = np.nan
    phantom.counting_efficiency[1, 0] = np.nan
    phantom.fraction_standard_error[1, 0] = np.nan
    phantom.sample_counts[:, 1] = 1
    phantom.counting_efficiency[:, 1] = 1
    phantom.fraction_standard_error[:, 1] = np.nan
    phantom.save(tmp_path)
    restored = Phantom.read_root(tmp_path / "water-sphere_sampling.root")
    for name in ("pdg_codes", "energy_fraction", "counting_efficiency",
                 "sample_counts", "fraction_standard_error", "fraction_variance",
                 "counting_variance", "counting_standard_error"):
        np.testing.assert_array_equal(getattr(restored, name), getattr(phantom, name))
    assert restored.metadata["example_provenance"] == phantom.metadata["example_provenance"]
    assert restored.radius_cm == phantom.radius_cm
    assert restored.density_g_cm3 == phantom.density_g_cm3
    assert not list(tmp_path.glob("*.npz"))


def test_core_state_does_not_depend_on_metadata(phantom, tmp_path):
    phantom.metadata.clear()
    assert "Precision complete:" in str(phantom)
    phantom.save(tmp_path)
    restored = Phantom.read_root(tmp_path / "water-sphere_sampling.root")
    assert restored.metadata == {}
    assert restored.precision_settings == phantom.precision_settings
    np.testing.assert_array_equal(restored.geometry.layers, phantom.geometry.layers)
    assert str(restored) == str(phantom)


def test_precision_record_is_independent_of_run_provenance(phantom, tmp_path):
    from dataclasses import FrozenInstanceError, replace
    with pytest.raises(FrozenInstanceError):
        phantom.precision_settings.relative_dose_tolerance = .1
    phantom.precision_settings = replace(phantom.precision_settings, relative_dose_tolerance=.1)
    phantom.save(tmp_path)
    restored = Phantom.read_root(tmp_path / "water-sphere_sampling.root")
    assert restored.precision_settings.relative_dose_tolerance == .1
    assert restored.metadata["sampling_settings"]["relative_dose_tolerance"] == .05


def test_precision_defaults_and_overrides_do_not_change_saved_target(phantom):
    saved = phantom.precision_settings
    explicit = phantom.precision(**asdict(saved))
    default = phantom.precision()
    overridden = phantom.precision(relative_dose_tolerance=.1)
    expected = phantom.precision(**asdict(replace(saved, relative_dose_tolerance=.1)))
    for key in explicit:
        np.testing.assert_array_equal(default[key], explicit[key])
        np.testing.assert_array_equal(overridden[key], expected[key])
    assert phantom.precision_settings is saved


def test_precision_without_saved_target_requires_complete_explicit_settings(phantom):
    saved = phantom.precision_settings
    expected = phantom.precision()
    phantom.precision_settings = None
    for kwargs in ({}, {"relative_dose_tolerance": .1}):
        with pytest.raises(ValueError, match="Without stored precision settings"):
            phantom.precision(**kwargs)
    actual = phantom.precision(**asdict(saved))
    for key in expected:
        np.testing.assert_array_equal(actual[key], expected[key])


@pytest.mark.parametrize("kwargs", [
    {"relative_dose_tolerance": 0}, {"absolute_dose_tolerance_Gy": -1},
    {"confidence_factor": float("nan")}, {"confidence_factor": float("inf")},
])
def test_precision_rejects_invalid_overrides(phantom, kwargs):
    with pytest.raises(ValueError, match="finite and positive"):
        phantom.precision(**kwargs)


def test_geometry_is_the_only_source_of_mass_and_radius(phantom, tmp_path):
    from atris_tools.psf import DENSITY, OUTER_RADIUS
    original_mass = phantom.mass_g
    phantom.geometry.layers[0, DENSITY] *= 2
    assert phantom.mass_g == pytest.approx(2 * original_mass)
    phantom.geometry.layers[0, OUTER_RADIUS] *= 2
    assert phantom.radius_cm == pytest.approx(30)
    assert phantom.mass_g == pytest.approx(16 * original_mass)
    phantom.save(tmp_path)
    restored = Phantom.read_root(tmp_path / "water-sphere_sampling.root")
    assert restored.mass_g == phantom.mass_g


def test_root_rejects_mass_inconsistent_with_geometry(phantom, tmp_path):
    phantom.save(tmp_path)
    path = tmp_path / "water-sphere_sampling.root"
    with uproot.open(path) as root:
        metadata = json.loads(str(root["metadata"]))
    metadata["mass_g"] *= 2
    with uproot.update(path) as root:
        root["metadata"] = json.dumps(metadata)
    with pytest.raises(ValueError, match="mass_g differs from its PSF geometry"):
        Phantom.read_root(path)


def test_notebook_gather_print_save_interface(phantom, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    name = "water-sphere"
    phantom = Phantom.gather(name)
    print(phantom)
    phantom.save()
    assert capsys.readouterr().out.startswith(name + ": radius ")
    assert Phantom.read_root(tmp_path / f"{name}_sampling.root").name == name


def test_sampling_root_reads_previous_tolerance_spelling(phantom, tmp_path):
    phantom.save(tmp_path)
    path = tmp_path / "water-sphere_sampling.root"
    with uproot.open(path) as root:
        metadata = json.loads(str(root["metadata"]))
    metadata["precision_settings"] = dict(
        relative_tolerance=.05, absolute_dose_tolerance_Gy=1e-12, confidence_factor=1.96)
    with uproot.update(path) as root:
        root["metadata"] = json.dumps(metadata)
    original = path.read_bytes()
    phantom = Phantom.read_root(path)
    assert phantom.precision_settings.relative_dose_tolerance == .05
    assert not hasattr(phantom.precision_settings, "relative_tolerance")
    assert "Precision complete:" in str(phantom)
    assert path.read_bytes() == original


def test_live_export_marks_unsampled_bins_without_inventing_zeros(
    phantom, tmp_path
):
    phantom.sample_counts[1, 0] = 0
    phantom.energy_fraction[1, 0] = np.nan
    phantom.counting_efficiency[1, 0] = np.nan
    phantom.fraction_standard_error[1, 0] = np.nan
    phantom.save(tmp_path, allow_partial=True)
    path = tmp_path / "water-sphere_response.txt"
    with pytest.raises(ValueError, match="finite"):
        PhantomTable.read(path)
    table = PhantomTable.read(path, allow_missing=True)
    assert np.isnan(table.coefficients[1, 0])
    assert table.metadata["sampling_status"] == "partial"
    import uproot
    with uproot.open(tmp_path / "water-sphere_sampling.root") as root:
        statistics = root["sampling"].arrays(library="np")
        assert statistics["sample_counts"][1, 0] == 0
        assert statistics["detected_counts"][1, 0] == 0
        assert np.isnan(statistics["fraction_variance"][1, 0])


def test_export_requires_photons_first(phantom, tmp_path):
    phantom.pdg_codes = np.array([2212, 22])
    with pytest.raises(ValueError, match="photons"):
        phantom.save(tmp_path / "export")


def test_one_sample_has_no_estimated_variance(phantom):
    phantom.sample_counts[:, 0] = 1
    phantom.fraction_standard_error[:, 0] = np.nan
    assert np.all(np.isnan(phantom.fraction_variance[:, 0]))
    assert np.all(np.isnan(phantom.counting_variance[:, 0]))
    assert np.all(np.isnan(phantom.counting_standard_error[:, 0]))


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
    response = Phantom.from_statistics(
        {22: incremental}, name="water-sphere", geometry=water_psf(4e-4)
    )
    np.testing.assert_array_equal(response.sample_counts, 4)
    np.testing.assert_allclose(response.counting_efficiency, 0.75)
    np.testing.assert_allclose(
        response.fraction_variance, np.var([0, 0.25, 0.5, 1], ddof=1)
    )
