"""Read AtRIS Planet Specification Format files."""

from pathlib import Path
import re

import numpy as np


def _locate_table(path):
    legacy_header = None
    with Path(path).open() as psf_file:
        for line_number, line in enumerate(psf_file):
            text = line.strip()
            if not text:
                continue
            if text.startswith("#"):
                if legacy_header is None:
                    legacy_header = text[1:].split()
                continue

            fields = text.split()
            try:
                float(fields[0])
            except ValueError:
                return fields, line_number + 1
            return legacy_header, line_number

    raise ValueError("PSF file contains no numeric table: " + str(path))


def read_psf_header(path):
    """Return the material-definition fields preceding the numeric table."""
    header, _ = _locate_table(path)
    if header is None:
        raise ValueError("PSF file contains no material definition: " + str(path))
    return header


def load_psf(path):
    """Return the numeric PSF table, skipping its descriptive and material headers."""
    _, data_start = _locate_table(path)
    return np.atleast_2d(np.loadtxt(path, skiprows=data_start))


def _compact_fractions(formula):
    parts = re.findall(r"([A-Z][a-z]*)(\d+)", formula)
    if not parts or "".join(element + weight for element, weight in parts) != formula:
        raise ValueError("Invalid compact PSF material formula: " + formula)
    total = sum(float(weight) for _, weight in parts)
    if total == 0:
        raise ValueError("PSF material formula has zero total weight: " + formula)
    return {element: float(weight) / total for element, weight in parts}


def read_psf_layers(path):
    """Return PSF rows as plotting-ready spherical material layers."""
    header = read_psf_header(path)
    data = load_psf(path)
    expected_columns = 10 + len(header)
    if data.shape[1] != expected_columns:
        raise ValueError(
            "%s has %i columns; expected %i from its material definition"
            % (Path(path).name, data.shape[1], expected_columns)
        )

    compact_fractions = _compact_fractions(header[0])
    material_names = header[1:]
    states = {0.0: "gas", 1.0: "solid", 2.0: "liquid"}
    layers = []
    for row in data:
        state = states.get(row[10], "gas")
        fractions = {
            name: fraction
            for name, fraction in zip(material_names, row[11:])
            if fraction != 0.0
        }
        if state == "solid" and not fractions:
            fractions = compact_fractions.copy()
        layers.append(
            {
                "rmin": row[0],
                "rmax": row[1],
                "detector_id": int(row[6]),
                "temperature": row[7],
                "density": row[8],
                "pressure": row[9],
                "state": state,
                "fractions": fractions,
            }
        )
    return layers
