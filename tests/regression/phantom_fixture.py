"""Explicit water material used by native transport regression tests."""
from atris_tools.psf import PSF


def water_psf(radius_cm=15):
    return PSF(inner_radius_km=0, outer_radius_km=radius_cm / 1e5,
               temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
               mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528},
               state="liquid")
