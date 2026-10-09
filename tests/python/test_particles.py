from pathlib import Path

import numpy as np
import pytest

from atris_tools.particles import (
    GEANT4_PARTICLES, ion_numbers, ion_pdg, particle_name, particle_source, pdg_code,
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


def test_all_supplied_phantom_species_have_source_settings():
    path = Path(__file__).resolve().parents[2] / "phantoms/MeV-valued/icru_zero_0.000MeV_detAB_response.txt"
    for code in np.loadtxt(path, max_rows=1, dtype=int):
        source = particle_source(code)
        if source["particle"] == "ion":
            assert ion_pdg(source["ion"]["Z"], source["ion"]["A"]) == code
        else:
            assert pdg_code(source["particle"]) == code
