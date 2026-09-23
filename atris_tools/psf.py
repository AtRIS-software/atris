"""Read AtRIS Planet Specification Format files."""

from pathlib import Path

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
