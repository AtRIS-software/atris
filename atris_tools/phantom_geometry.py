"""Spherical phantom layers and shared detector/source conventions.

The source covers the projected disk with a parallel beam. Two outer shells
terminate escaped tracks; they are not part of the physical phantom.
"""

import numpy as np

from .psf import (
    DENSITY,
    DETECTOR_ID,
    INNER_RADIUS,
    OUTER_RADIUS,
    PHI_END,
    PHI_START,
    PSF,
    THETA_END,
    THETA_START,
)


PHANTOM_DETECTOR_ID = 1
DETECTOR_LAYER = 0
CM_PER_KM = 1e5
SPHERE_ANGLE_TOLERANCE = 1e-10
SOURCE_DISTANCE_RADII = 1.1
TERMINATION_DETECTOR_IDS = (0, 2)
TERMINATION_INNER_RADII = (2, 2.2)
TERMINATION_OUTER_RADII = (2.1, 2.3)
WORLD_MARGIN_RADII = 1.7
VACUUM_DENSITY_G_CM3 = 1e-25


def sphere_psf(path, *, transport=False):
    """Read spherical physical layers, preserving the supplied PSF materials."""
    psf = path if isinstance(path, PSF) else PSF.read(path)
    if transport:
        layers = psf.layers[~np.isin(psf.layers[:, DETECTOR_ID], TERMINATION_DETECTOR_IDS)]
    else:
        layers = psf.layers
    if not len(layers) or not np.isfinite(layers).all():
        raise ValueError("The PSF must contain finite spherical layers")
    if np.any(layers[:, INNER_RADIUS] < 0) or np.any(layers[:, OUTER_RADIUS] <= layers[:, INNER_RADIUS]) or np.any(
        layers[1:, INNER_RADIUS] < layers[:-1, OUTER_RADIUS]
    ):
        raise ValueError("PSF layers must be ordered without overlap and have positive thickness")
    if not np.allclose(layers[:, [PHI_START, PHI_END, THETA_START, THETA_END]],
                       [0, 2 * np.pi, 0, np.pi], rtol=0, atol=SPHERE_ANGLE_TOLERANCE):
        raise ValueError("The PSF must cover a complete sphere")
    if np.any(layers[:, DENSITY] <= 0):
        raise ValueError("Phantom density must be positive")
    return PSF.from_layers(layers.copy(), psf.materials)
