"""Phantom table I/O following LoadPhantoms in src/main.cc.

Coefficients are read unchanged. The C++ scorer interprets radiation values
as energy fractions and counting values as efficiencies; comments do not
change that interpretation.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .phantoms import (
    RESPONSE_ENERGY_BINS,
    RESPONSE_ENERGY_MIN_MEV,
    RESPONSE_ENERGY_MAX_MEV,
)

ENERGY_EDGES_MEV = np.geomspace(
    RESPONSE_ENERGY_MIN_MEV,
    RESPONSE_ENERGY_MAX_MEV,
    RESPONSE_ENERGY_BINS + 1,
)
# Arithmetic bin centres match the archived phantom analysis.
ENERGY_CENTRES_MEV = (ENERGY_EDGES_MEV[:-1] + ENERGY_EDGES_MEV[1:]) / 2
ENERGY_FRACTION = "energy_fraction"
COUNTING_EFFICIENCY = "counting_efficiency"


@dataclass
class PhantomTable:
    """One radiation or counting matrix, with its signed PDG row identifiers.

    Coefficients retain their file values. ``quantity`` describes how the C++
    scorer uses them, not a unit inferred from the file. Metadata is descriptive
    and does not control reading or scoring.
    """

    pdg_codes: np.ndarray
    coefficients: np.ndarray
    quantity: str = ENERGY_FRACTION
    metadata: dict = field(default_factory=dict)
    # Calibration builds can explicitly retain NaN for not-yet-sampled bins.
    allow_missing: bool = False

    def __post_init__(self):
        self.pdg_codes = np.asarray(self.pdg_codes)
        self.coefficients = np.asarray(self.coefficients, dtype=float)
        if (
            self.pdg_codes.ndim != 1
            or not self.pdg_codes.size
            or not np.issubdtype(self.pdg_codes.dtype, np.integer)
            or len(set(self.pdg_codes)) != self.pdg_codes.size
        ):
            raise ValueError("Use a nonempty header of unique integer PDG codes")
        if self.quantity not in (ENERGY_FRACTION, COUNTING_EFFICIENCY):
            raise ValueError(
                "Internal tables use energy_fraction or counting_efficiency"
            )
        if self.coefficients.shape != (self.pdg_codes.size, RESPONSE_ENERGY_BINS):
            raise ValueError("Each particle row must contain exactly 650 coefficients")
        if (
            np.any(np.isinf(self.coefficients))
            or np.any(self.coefficients < 0)
            or (not self.allow_missing and np.any(np.isnan(self.coefficients)))
        ):
            raise ValueError("Phantom coefficients must be finite and nonnegative")
        if self.quantity == COUNTING_EFFICIENCY and np.any(self.coefficients > 1):
            raise ValueError("Counting efficiencies must lie in [0, 1]")

    @property
    def deposited_energy_MeV(self):
        """Scorer response at bin centres, assuming energy-fraction inputs."""
        if self.quantity != ENERGY_FRACTION:
            raise ValueError("A counting table does not contain deposited energies")
        return self.coefficients * ENERGY_CENTRES_MEV

    @classmethod
    def read(cls, path, *, counting=False, allow_missing=False):
        """Read raw coefficients; comments never select units or rescale values."""
        path = Path(path)
        lines = path.read_text().splitlines()
        if not lines:
            raise ValueError(f"Empty phantom table: {path.name}")
        header_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.strip() and not line.lstrip().startswith("#")
            ),
            None,
        )
        if header_index is None:
            raise ValueError(f"Missing PDG header: {path.name}")
        codes = np.array(
            [int(value) for value in lines[header_index].split("#", 1)[0].split()],
            dtype=int,
        )
        # C++ consumes a flat coefficient stream; line breaks do not define rows.
        values = " ".join(line.split("#", 1)[0] for line in lines[header_index + 1 :])
        data = np.array(values.split(), dtype=float)
        if data.size != codes.size * RESPONSE_ENERGY_BINS:
            raise ValueError(
                f"{path.name}: expected {codes.size * RESPONSE_ENERGY_BINS} coefficients"
            )
        data = data.reshape(codes.size, RESPONSE_ENERGY_BINS)
        metadata = {}
        for line in lines:
            if line.lstrip().startswith("#"):
                key, separator, value = line.lstrip()[1:].partition(":")
                if separator:
                    metadata[key.strip()] = value.strip()
        return cls(
            codes,
            data,
            COUNTING_EFFICIENCY if counting else ENERGY_FRACTION,
            metadata,
            allow_missing=allow_missing,
        )

    def write(self, path, **savetxt_kwargs):
        """Write comment metadata followed by the PDG header and coefficients."""
        if {"header", "comments", "delimiter", "footer"} & savetxt_kwargs.keys():
            raise ValueError("The phantom header and whitespace layout are fixed")
        metadata = {
            "layout": "first non-comment line lists PDG codes; one coefficient row per code in that order",
            "particle_rows": self.pdg_codes.size,
            "energy_bins": RESPONSE_ENERGY_BINS,
            "incident_energy_unit": "MeV; total kinetic energy of the particle, not energy per nucleon",
            "energy_grid": f"log-uniform edges from {ENERGY_EDGES_MEV[0]:g} to {ENERGY_EDGES_MEV[-1]:g} MeV",
            "energy_log10_step": f"{np.log10(ENERGY_EDGES_MEV[1] / ENERGY_EDGES_MEV[0]):g}",
            "energy_bin_centres": "arithmetic mean of adjacent edges",
            "atris_quantity": self.quantity,
            "coefficient_unit": "1 (dimensionless)",
            "coefficient_definition": (
                "probability of meeting the counting criterion"
                if self.quantity == COUNTING_EFFICIENCY
                else "deposited-energy fraction of incident kinetic energy; see response_definition for the scored deposit"
            ),
        }
        metadata.update(
            {key: value for key, value in self.metadata.items() if key not in metadata}
        )
        header = "# AtRIS phantom table\n"
        header += "\n".join(f"# {key}: {value}" for key, value in metadata.items())
        header += "\n" + " ".join(map(str, self.pdg_codes))
        np.savetxt(
            path, self.coefficients, header=header, comments="", **savetxt_kwargs
        )
