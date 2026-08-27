import re
import shutil
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest

from atris_tools.atrismacrogen import macroGenManager
from atris_tools.simtools import psf2gdml


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


def prepare_run(path):
    shutil.copyfile(FIXTURE / "simulation.psf", path / "simulation.psf")
    shutil.copyfile(FIXTURE / "simulation.gdml", path / "simulation.gdml")


def test_macro_generation_is_reproducible_and_preserves_requested_counts(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    prepare_run(first)
    prepare_run(second)

    arguments = dict(
        partspb=2,
        alphafactor=0.5,
        random_seed=20260827,
        energy_min_power=0,
        energy_max_power=2,
        energy_points=3,
    )
    macroGenManager(output_dir=first, **arguments)
    macroGenManager(output_dir=second, **arguments)

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
    assert "/gps/pos/radius 1.001 km" in proton_macro
    assert re.search(r"^/random/setSeeds \d{2,6} \d{2,6}$", proton_macro, re.MULTILINE)
    assert re.search(r"^/random/setSeeds \d{2,6} \d{2,6}$", alpha_macro, re.MULTILINE)

    np.testing.assert_allclose(np.loadtxt(first / "protons.bins"), [1, 10, 100])
    np.testing.assert_allclose(np.loadtxt(first / "alphas.bins"), [4, 40, 400])


def test_macro_generation_rejects_too_short_energy_grid(tmp_path):
    with pytest.raises(ValueError, match="at least 2"):
        macroGenManager(1, output_dir=tmp_path, energy_points=1)


def test_psf_conversion_preserves_reviewed_layer_geometry(tmp_path, monkeypatch):
    shutil.copyfile(FIXTURE / "simulation.psf", tmp_path / "simulation.psf")
    monkeypatch.chdir(tmp_path)

    psf2gdml()

    generated = ElementTree.parse(tmp_path / "simulation.gdml").getroot()
    reviewed = ElementTree.parse(FIXTURE / "simulation.gdml").getroot()

    def layer_geometry(root):
        return [
            (sphere.attrib["rmin"], sphere.attrib["rmax"])
            for sphere in root.findall("./solids/sphere")
        ]

    assert layer_geometry(generated) == [
        ("0.000000", "1.000000"),
        ("1.000000", "2.000000"),
    ]
    assert layer_geometry(reviewed) == [("0", "1"), ("1", "2")]
    assert [
        auxiliary.attrib["auxvalue"]
        for auxiliary in generated.findall("./structure/volume/auxiliary")
    ] == ["0", "1"]
