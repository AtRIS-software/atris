"""Particle labels, PDG codes, and Geant4 source settings used by AtRIS."""

from operator import index
import re

ION_PDG_BASE = 1_000_000_000
ION_Z_SCALE = 10_000
ION_A_SCALE = 10
ION_FIELD_BASE = 1_000

GEANT4_PARTICLES = {
    "gamma": 22,
    "proton": 2212,
    "anti_proton": -2212,
    "e-": 11,
    "e+": -11,
    "mu-": 13,
    "mu+": -13,
    "neutron": 2112,
    "anti_neutron": -2112,
    "pi+": 211,
    "pi-": -211,
    "pi0": 111,
    "kaon+": 321,
    "kaon-": -321,
    "deuteron": 1000010020,
    "triton": 1000010030,
    "He3": 1000020030,
    "alpha": 1000020040,
}
_GEANT4_NAMES = {code: name for name, code in GEANT4_PARTICLES.items()}


def ion_pdg(Z, A):
    """PDG code for an ordinary ground-state nucleus (no hypernuclei)."""
    Z, A = index(Z), index(A)
    if not 1 <= Z <= A < ION_FIELD_BASE:
        raise ValueError("Use 1 <= Z <= A < 1000")
    return ION_PDG_BASE + ION_Z_SCALE * Z + ION_A_SCALE * A


def _nuclear_fields(pdg):
    code = abs(index(pdg))
    Z = (code // ION_Z_SCALE) % ION_FIELD_BASE
    A = (code // ION_A_SCALE) % ION_FIELD_BASE
    return Z, A


def ion_numbers(pdg):
    """Return (Z, A) for an ordinary ground-state nucleus or antinucleus."""
    code = abs(index(pdg))
    Z, A = _nuclear_fields(code)
    if ion_pdg(Z, A) != code:
        raise ValueError("Expected an ordinary ground-state nuclear PDG code")
    return Z, A


def pdg_code(name):
    """Resolve a particle name, integer PDG code, or explicit isotope.

    Isotopes accept Fe-56, iron-56, Fe56, 56Fe, or (element, A), where
    element is an atomic number, symbol, or name.
    """
    if isinstance(name, tuple):
        if len(name) != 2:
            raise ValueError("An isotope pair contains (element, mass number)")
        element, mass = name
        if isinstance(element, str):
            atomic_number = ISOTOPE_ATOMIC_NUMBERS.get(element.strip().lower())
            if atomic_number is None:
                raise ValueError(f"Unknown element {element!r}")
        else:
            atomic_number = element
        return ion_pdg(atomic_number, mass)
    if not isinstance(name, str):
        return index(name)
    name = name.strip()
    if name in GEANT4_PARTICLES:
        return GEANT4_PARTICLES[name]
    for code, label in PARTICLE_NAMES.items():
        if name == label:
            return code
    isotope = re.fullmatch(r"([A-Za-z]+)[\s-]*(\d+)", name)
    mass_first = re.fullmatch(r"(\d+)\s*([A-Za-z]+)", name)
    if mass_first:
        mass, element = mass_first.groups()
        return pdg_code((element, int(mass)))
    if isotope:
        element, mass = isotope.groups()
        atomic_number = ISOTOPE_ATOMIC_NUMBERS.get(element.lower())
        if atomic_number is not None:
            return ion_pdg(atomic_number, int(mass))
    raise ValueError(f"Unknown particle {name!r}; expected a particle name or isotope such as Fe-56")


def particle_source(pdg, *, charge=None):
    """Return Geant4 particle-source keyword arguments for this PDG code.

    Named light nuclei use their Geant4 names. Other positive ground-state
    nuclei use /gps/ion, fully stripped unless charge is supplied explicitly.
    Charge is in elementary-charge units and does not alter the nuclear PDG.
    """
    pdg = index(pdg)
    if charge is None and pdg in _GEANT4_NAMES:
        return {"particle": _GEANT4_NAMES[pdg]}
    if pdg < ION_PDG_BASE:
        raise ValueError(
            "No source mapping for this code/charge; charge applies to positive nuclei"
        )
    Z, A = ion_numbers(pdg)
    charge = Z if charge is None else index(charge)
    if not 0 <= charge <= Z:
        raise ValueError("Use 0 <= charge <= Z")
    return {"particle": "ion", "ion": {"Z": Z, "A": A, "charge": charge}}


PARTICLE_NAMES = {
    22: "photon",
    2212: "proton",
    -2212: "antiproton",
    2112: "neutron",
    -2112: "antineutron",
    11: "electron",
    -11: "positron",
    13: "muon-",
    -13: "muon+",
    211: "pion+",
    -211: "pion-",
    111: "pion0",
    321: "kaon+",
    -321: "kaon-",
}
PARTICLE_SYMBOLS = {
    22: r"$\gamma$",
    2212: r"$p$",
    -2212: r"$\bar{p}$",
    2112: r"$n$",
    -2112: r"$\bar{n}$",
    11: r"$e^{-}$",
    -11: r"$e^{+}$",
    12: r"$\nu_e$",
    -12: r"$\bar{\nu}_e$",
    13: r"$\mu^{-}$",
    -13: r"$\mu^{+}$",
    14: r"$\nu_\mu$",
    -14: r"$\bar{\nu}_\mu$",
    15: r"$\tau^{-}$",
    -15: r"$\tau^{+}$",
    16: r"$\nu_\tau$",
    -16: r"$\bar{\nu}_\tau$",
    211: r"$\pi^{+}$",
    -211: r"$\pi^{-}$",
    111: r"$\pi^{0}$",
    321: r"$K^{+}$",
    -321: r"$K^{-}$",
}
ELEMENT_SYMBOLS = (
    "n",
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
)
ELEMENT_ATOMIC_NUMBERS = {
    symbol: atomic_number
    for atomic_number, symbol in enumerate(ELEMENT_SYMBOLS)
    if atomic_number > 0
}
ELEMENT_NAMES = (
    "", "hydrogen", "helium", "lithium", "beryllium", "boron", "carbon",
    "nitrogen", "oxygen", "fluorine", "neon", "sodium", "magnesium",
    "aluminium", "silicon", "phosphorus", "sulfur", "chlorine", "argon",
    "potassium", "calcium", "scandium", "titanium", "vanadium", "chromium",
    "manganese", "iron", "cobalt", "nickel",
)
ISOTOPE_ATOMIC_NUMBERS = {
    label.lower(): number
    for labels in (ELEMENT_SYMBOLS, ELEMENT_NAMES)
    for number, label in enumerate(labels) if number > 0
}
ISOTOPE_ATOMIC_NUMBERS.update(aluminum=ELEMENT_ATOMIC_NUMBERS["Al"],
                              sulphur=ELEMENT_ATOMIC_NUMBERS["S"])


def particle_name(pdg_code):
    if pdg_code in PARTICLE_NAMES:
        return PARTICLE_NAMES[pdg_code]
    absolute_code = abs(pdg_code)
    if absolute_code >= ION_PDG_BASE:
        atomic_number, mass_number = _nuclear_fields(pdg_code)
        element = (
            ELEMENT_SYMBOLS[atomic_number]
            if atomic_number < len(ELEMENT_SYMBOLS)
            else "Z%i" % atomic_number
        )
        prefix = "anti-" if pdg_code < 0 else ""
        return "%s%s-%i" % (prefix, element, mass_number)
    return str(pdg_code)


def particle_symbol(pdg_code):
    if pdg_code in PARTICLE_SYMBOLS:
        return PARTICLE_SYMBOLS[pdg_code]
    absolute_code = abs(pdg_code)
    if absolute_code >= ION_PDG_BASE:
        atomic_number, mass_number = _nuclear_fields(pdg_code)
        element = (
            ELEMENT_SYMBOLS[atomic_number]
            if atomic_number < len(ELEMENT_SYMBOLS)
            else "Z%i" % atomic_number
        )
        if pdg_code < 0:
            return r"$^{%i}\overline{\mathrm{%s}}$" % (
                mass_number,
                element,
            )
        return r"$^{%i}\mathrm{%s}$" % (mass_number, element)
    return str(pdg_code)
