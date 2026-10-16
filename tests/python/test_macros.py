import re
import shutil
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest

import atris_tools.gdml as gdml_module
import atris_tools.macros as macros_module
from atris_tools.macros import generate_macros, read_macro
from atris_tools.gdml import psf_to_gdml


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


@pytest.mark.parametrize("points", ["", "/gps/hist/point 1 0\n/gps/hist/point 10 1 # weight\n"])
def test_read_macro_preserves_points_and_last_setting(tmp_path, points):
    path = tmp_path / "simulation.mac"
    path.write_text("# comment\n/run/beamOn 1\n" + points + "/run/beamOn 20 # events\n")
    settings, energy_points = read_macro(path)
    assert settings == {"/run/beamOn": "20"}
    np.testing.assert_array_equal(
        energy_points, np.array([[1, 0], [10, 1]]) if points else np.empty((0, 2))
    )


def prepare_run(path):
    shutil.copyfile(FIXTURE / "simulation.psf", path / "simulation.psf")
    shutil.copyfile(FIXTURE / "simulation.gdml", path / "simulation.gdml")


@pytest.mark.parametrize("interface", ["python", "cli"])
def test_macro_defaults_generate_expected_sampling(tmp_path, monkeypatch, interface):
    prepare_run(tmp_path)
    if interface == "python":
        written = generate_macros(run_directory=tmp_path)
        assert set(written) == {tmp_path / name for name in macros_module.GENERATED_INPUTS}
        assert all(path.is_file() for path in written)
    else:
        monkeypatch.setattr("sys.argv", ["atris-generate-macros", str(tmp_path)])
        macros_module.main()

    proton_bins = np.loadtxt(tmp_path / "protons.bins")
    np.testing.assert_allclose(proton_bins, np.logspace(0, 6, 121))
    np.testing.assert_allclose(np.loadtxt(tmp_path / "alphas.bins"), 4 * proton_bins)
    for species, events in [("protons", 605000), ("alphas", 399300)]:
        macro = (tmp_path / f"{species}.mac").read_text()
        assert f"/run/beamOn {events}\n" in macro
        assert f"/gps/pos/radius {1.001:.17e} km\n" in macro
        assert "/gps/ang/type cos\n" in macro
        assert "/run/setCut 100. m\n" in macro
    assert not (tmp_path / "phantoms.txt").exists()


def test_macro_generation_is_reproducible_and_preserves_requested_counts(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    prepare_run(first)
    prepare_run(second)

    arguments = dict(
        particles_per_bin=2,
        alpha_factor=0.5,
        random_seed=20260827,
        energy_min_power=0,
        energy_max_power=2,
        energy_points=3,
    )
    generate_macros(run_directory=first, **arguments)
    generate_macros(run_directory=second, **arguments)

    for species in ("protons", "alphas"):
        assert (first / f"{species}.mac").read_bytes() == (
            second / f"{species}.mac"
        ).read_bytes()
        assert (first / f"{species}.bins").read_bytes() == (
            second / f"{species}.bins"
        ).read_bytes()
        assert (first / f"{species}.gdml").read_bytes() == (
            first / "simulation.gdml"
        ).read_bytes()

    proton_macro = (first / "protons.mac").read_text()
    alpha_macro = (first / "alphas.mac").read_text()
    assert "/gps/particle proton" in proton_macro
    assert "/gps/particle alpha" in alpha_macro
    assert "/run/beamOn 6" in proton_macro
    assert "/run/beamOn 3" in alpha_macro
    assert f"/gps/pos/radius {1.001:.17e} km" in proton_macro
    assert re.search(r"^/random/setSeeds \d{2,6} \d{2,6}$", proton_macro, re.MULTILINE)
    assert re.search(r"^/random/setSeeds \d{2,6} \d{2,6}$", alpha_macro, re.MULTILINE)

    np.testing.assert_allclose(np.loadtxt(first / "protons.bins"), [1, 10, 100])
    np.testing.assert_allclose(np.loadtxt(first / "alphas.bins"), [4, 40, 400])


def test_macro_generation_rejects_too_short_energy_grid(tmp_path):
    with pytest.raises(ValueError, match="at least 2"):
        generate_macros(1, run_directory=tmp_path, energy_points=1)


def test_macro_generation_refuses_existing_inputs_before_writing(tmp_path):
    prepare_run(tmp_path)
    existing = tmp_path / "protons.mac"
    existing.write_text("keep me\n")

    with pytest.raises(FileExistsError, match="protons.mac"):
        generate_macros(2, run_directory=tmp_path, energy_points=3)

    assert existing.read_text() == "keep me\n"
    assert not (tmp_path / "protons.bins").exists()
    assert not (tmp_path / "protons.gdml").exists()
    assert not (tmp_path / "alphas.mac").exists()
    assert not (tmp_path / "alphas.bins").exists()
    assert not (tmp_path / "alphas.gdml").exists()


def test_psf_conversion_preserves_reviewed_layer_geometry(tmp_path, monkeypatch):
    shutil.copyfile(FIXTURE / "simulation.psf", tmp_path / "simulation.psf")

    psf_to_gdml(tmp_path / "simulation.psf")

    generated = ElementTree.parse(tmp_path / "simulation.gdml").getroot()
    reviewed = ElementTree.parse(FIXTURE / "simulation.gdml").getroot()

    def layer_geometry(root):
        return [
            (float(sphere.attrib["rmin"]), float(sphere.attrib["rmax"]))
            for sphere in root.findall("./solids/sphere")
        ]

    assert layer_geometry(generated) == [
        (0, 1),
        (1, 2),
    ]
    assert layer_geometry(reviewed) == [(0, 1), (1, 2)]
    assert [
        auxiliary.attrib["auxvalue"]
        for auxiliary in generated.findall("./structure/volume/auxiliary")
    ] == ["0", "1"]
    legacy_material = generated.find("./materials/material[@name='material0']")
    assert legacy_material.attrib["state"] == "solid"
    assert [
        (fraction.attrib["ref"], float(fraction.attrib["n"]))
        for fraction in legacy_material.findall("fraction")
    ] == [("G4_H", 1.0)]


@pytest.mark.parametrize(
    ("state_code", "fractions", "expected_state"),
    [
        (0, (0.75, 0.25), "gas"),
        (1, (0.25, 0.75), "solid"),
        (2, (0.1119, 0.8881), "liquid"),
    ],
)
def test_psf_conversion_uses_explicit_composition_for_every_state(
    tmp_path, state_code, fractions, expected_state
):
    psf = tmp_path / "simulation.psf"
    psf.write_text(
        "H1000 H O\n"
        "0 1 0 6.283185 0 3.141593 0 293.15 1 101325 "
        f"{state_code} {fractions[0]} {fractions[1]}\n"
    )

    output = psf_to_gdml(psf)

    root = ElementTree.parse(output).getroot()
    material = root.find("./materials/material[@name='material0']")
    assert material.attrib["state"] == expected_state
    assert [
        (fraction.attrib["ref"], float(fraction.attrib["n"]))
        for fraction in material.findall("fraction")
    ] == [("G4_H", fractions[0]), ("G4_O", fractions[1])]


def test_psf_conversion_accepts_named_input(tmp_path, monkeypatch):
    input_path = tmp_path / "mercury.psf"
    shutil.copyfile(FIXTURE / "simulation.psf", input_path)
    monkeypatch.setattr(
        "sys.argv", ["atris-psf-to-gdml", str(input_path)]
    )

    gdml_module.main()

    assert (tmp_path / "mercury.gdml").is_file()


def test_psf_conversion_accepts_output_path(tmp_path, monkeypatch):
    input_path = tmp_path / "mercury.psf"
    output_path = tmp_path / "geometry.gdml"
    shutil.copyfile(FIXTURE / "simulation.psf", input_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "atris-psf-to-gdml",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    gdml_module.main()

    assert output_path.is_file()
