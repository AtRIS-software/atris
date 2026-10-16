from pathlib import Path

import numpy as np
import pytest

from atris_tools.particles import (
    GEANT4_PARTICLES,
    ion_numbers,
    ion_pdg,
    particle_name,
    particle_source,
    pdg_code,
)


def test_named_particle_lookup_round_trip():
    for name, code in GEANT4_PARTICLES.items():
        assert pdg_code(name) == code
        assert particle_source(code) == {"particle": name}
    assert pdg_code("electron") == 11
    assert pdg_code("antiproton") == -2212
    with pytest.raises(ValueError, match="Unknown"):
        pdg_code("made-up")


def test_ion_identity_and_charge_are_separate():
    code = ion_pdg(6, 12)
    assert code == 1000060120
    assert ion_numbers(code) == (6, 12)
    assert particle_name(code) == "C-12"
    assert particle_source(code) == {"particle": "ion", "ion": {"Z": 6, "A": 12, "charge": 6}}
    assert particle_source(code, charge=4)["ion"]["charge"] == 4
    assert particle_source(pdg_code("alpha"), charge=1)["ion"] == {"Z": 2, "A": 4, "charge": 1}
    with pytest.raises(ValueError):
        ion_numbers(code + 1)  # Excited-state numbering is not a ground-state ion.
    with pytest.raises(ValueError):
        particle_source(code, charge=7)
    with pytest.raises(ValueError):
        particle_source(11, charge=1)


@pytest.mark.parametrize("name,Z,A", [
    ("nickel-58", 28, 58), ("iron-56", 26, 56), ("Ni-58", 28, 58),
    ("oxygen-16", 8, 16), ("hydrogen-1", 1, 1), ("ALUMINIUM-27", 13, 27),
    ("Fe56", 26, 56), ("56Fe", 26, 56), ("Fe 56", 26, 56),
    ((26, 56), 26, 56), (("Fe", 56), 26, 56), (("iron", 56), 26, 56),
    ((np.int64(26), np.int64(56)), 26, 56),
])
def test_isotope_name_lookup(name, Z, A):
    assert pdg_code(name) == ion_pdg(Z, A)


@pytest.mark.parametrize("name", ["nickel-1", "nickel-0", "madeup-58", "nickel", "Ni-1000"])
def test_invalid_isotope_names(name):
    with pytest.raises(ValueError):
        pdg_code(name)


@pytest.mark.parametrize("species", [(26,), (26, 56, 0), ("madeup", 56), (26, 1)])
def test_invalid_isotope_pairs(species):
    with pytest.raises(ValueError):
        pdg_code(species)


def test_numeric_species_codes():
    assert pdg_code(22) == 22
    assert pdg_code(np.int64(1000260560)) == ion_pdg(26, 56)
    with pytest.raises(TypeError):
        pdg_code(22.5)


def test_all_supplied_phantom_species_have_source_settings():
    path = Path(__file__).resolve().parents[2] / "phantoms/MeV-valued/icru_zero_0.000MeV_detAB_response.txt"
    for code in np.loadtxt(path, max_rows=1, dtype=int):
        source = particle_source(code)
        if source["particle"] == "ion":
            assert ion_pdg(source["ion"]["Z"], source["ion"]["A"]) == code
        else:
            assert pdg_code(source["particle"]) == code
