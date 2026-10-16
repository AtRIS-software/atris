"""Sampled phantom responses, precision targets and result persistence."""

from dataclasses import asdict, astuple, dataclass, field
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json

import numpy as np
import uproot

from .file_io import atomic_text_output
from .particles import pdg_code
from .phantom_geometry import (
    CM_PER_KM,
    DETECTOR_LAYER,
    PHANTOM_DETECTOR_ID,
    SOURCE_DISTANCE_RADII,
    sphere_psf,
)
from .phantom_statistics import PhantomStatistics
from .phantom_table import (
    COUNTING_EFFICIENCY,
    ENERGY_EDGES_MEV,
    PhantomTable,
    RESPONSE_ENERGY_BINS,
)
from .psf import DENSITY, INNER_RADIUS, OUTER_RADIUS, PSF
from .root_records import read_ntuple


PHOTON_PDG = pdg_code("photon")
JOULES_PER_MEV = 1.602176634e-13
KG_PER_GRAM = 1e-3
ROOT_STATISTICS_RTOL = 1e-14


@dataclass(frozen=True)
class DosePrecision:
    relative_dose_tolerance: float
    absolute_dose_tolerance_Gy: float
    confidence_factor: float

    @classmethod
    def from_dict(cls, settings):
        """Read persisted targets, including the previous tolerance spelling."""
        settings = dict(settings)
        if "relative_tolerance" in settings:
            value = settings.pop("relative_tolerance")
            if "relative_dose_tolerance" in settings and settings["relative_dose_tolerance"] != value:
                raise ValueError("Conflicting relative dose tolerances")
            settings["relative_dose_tolerance"] = value
        return cls(**settings)

    def __post_init__(self):
        if not all(np.isfinite(value) and value > 0 for value in (
            self.relative_dose_tolerance, self.absolute_dose_tolerance_Gy, self.confidence_factor
        )):
            raise ValueError("Dose precision settings must be finite and positive")


@dataclass
class Phantom:
    """Sampled sphere responses on the AtRIS grid, one row per PDG code.

    Energy fractions are per intercepted primary, including its secondaries.
    Missing samples remain NaN and cannot be exported as measured zeroes.
    """

    pdg_codes: np.ndarray
    energy_fraction: np.ndarray
    counting_efficiency: np.ndarray
    sample_counts: np.ndarray
    fraction_standard_error: np.ndarray
    threshold_MeV: float
    metadata: dict = field(default_factory=dict)
    name: str = field(kw_only=True)
    geometry: PSF = field(kw_only=True)
    precision_settings: DosePrecision | None = field(default=None, kw_only=True)

    def __str__(self):
        lines = [
            f"{self.name}: radius {self.radius_cm:g} cm, density {self.density_g_cm3:g} g/cm^3",
            f"Incident species: {len(self.pdg_codes)}",
            f"Primaries retained: {self.sample_counts.sum():,}",
            f"Sampled bins: {np.count_nonzero(self.sample_counts):,}/{self.sample_counts.size:,}",
        ]
        if self.precision_settings is not None:
            quality = self.precision()
            lines.extend([
                f"Resolved energy bins: {quality['resolved'].sum():,}",
                f"Passing energy bins: {quality['passed'].sum():,}",
                f"Precision complete: {bool(quality['passed'].all())}",
            ])
        return "\n".join(lines)

    def precision(self, *, relative_dose_tolerance=None, absolute_dose_tolerance_Gy=None,
                  confidence_factor=None):
        """Use stored targets unless overridden, without changing those settings."""
        parameters = (relative_dose_tolerance, absolute_dose_tolerance_Gy, confidence_factor)
        if self.precision_settings is not None:
            parameters = tuple(default if value is None else value for default, value
                               in zip(astuple(self.precision_settings), parameters))
        if any(value is None for value in parameters):
            raise ValueError("Without stored precision settings, supply relative_dose_tolerance, "
                             "absolute_dose_tolerance_Gy and confidence_factor")
        settings = DosePrecision(*parameters)
        factor = self.dose_per_fraction_Gy
        dose = self.energy_fraction * factor
        error = self.fraction_standard_error * factor
        resolved = (self.sample_counts > 1) & np.isfinite(error) & (dose > 0)
        target = np.maximum(settings.absolute_dose_tolerance_Gy,
                            settings.relative_dose_tolerance * np.abs(dose))
        ratio = settings.confidence_factor * error / target
        passed = resolved & (ratio <= 1)
        return dict(dose=dose, dose_error=error, ratio=ratio, resolved=resolved, passed=passed)

    @classmethod
    def from_statistics(
        cls, statistics, *, name, geometry, threshold_MeV=0.0, metadata=None,
        precision_settings=None,
    ):
        """Build response rows from a PDG-to-statistics mapping, preserving order."""
        counts = np.array([s.sample_counts for s in statistics.values()])
        means = np.array([s.mean_fraction for s in statistics.values()])
        means[counts == 0] = np.nan
        detected = np.array([s.detected_counts for s in statistics.values()])
        efficiency = np.divide(
            detected, counts, out=np.full_like(means, np.nan), where=counts > 0
        )
        deviations = np.array([s.squared_deviations for s in statistics.values()])
        error = np.sqrt(
            np.divide(
                deviations,
                counts * (counts - 1),
                out=np.full_like(means, np.nan),
                where=counts > 1,
            )
        )
        return cls(
            np.array(list(statistics)),
            means,
            efficiency,
            counts,
            error,
            threshold_MeV,
            metadata or {},
            name=name,
            geometry=geometry,
            precision_settings=precision_settings,
        )

    @property
    def radius_cm(self):
        return float(self.geometry.layers[DETECTOR_LAYER, OUTER_RADIUS] * CM_PER_KM)

    @property
    def inner_radius_cm(self):
        return float(self.geometry.layers[DETECTOR_LAYER, INNER_RADIUS] * CM_PER_KM)

    @property
    def density_g_cm3(self):
        return float(self.geometry.layers[DETECTOR_LAYER, DENSITY])

    @property
    def source_radius_cm(self):
        return float(self.geometry.layers[-1, OUTER_RADIUS] * CM_PER_KM)

    @property
    def mass_g(self):
        return 4 / 3 * np.pi * (self.radius_cm**3 - self.inner_radius_cm**3) * self.density_g_cm3

    @property
    def area_cm2(self):
        """Area for AtRIS's two-direction interface-crossing normalization."""
        return 2 * np.pi * self.source_radius_cm**2

    @property
    def dose_per_fraction_Gy(self):
        """Dose corresponding to unit deposited-energy fraction in each bin."""
        centres = (ENERGY_EDGES_MEV[:-1] + ENERGY_EDGES_MEV[1:]) / 2
        return centres * JOULES_PER_MEV / (self.mass_g * KG_PER_GRAM)

    @property
    def detected_counts(self):
        """Primaries whose ionizing deposit exceeds the counting threshold."""
        return np.rint(np.where(self.sample_counts > 0,
            self.counting_efficiency * self.sample_counts, 0)).astype(np.int64)

    @property
    def fraction_variance(self):
        """Sample variance of individual energy fractions, not their mean."""
        return self.fraction_standard_error**2 * self.sample_counts

    @property
    def counting_variance(self):
        """Sample variance of the binary counting result; NaN when N < 2."""
        n = self.sample_counts
        p = self.counting_efficiency
        return np.divide(
            n * p * (1 - p), n - 1, out=np.full_like(p, np.nan), where=n > 1
        )

    @property
    def counting_standard_error(self):
        """Standard error of the sampled counting efficiency."""
        return np.sqrt(
            np.divide(
                self.counting_variance,
                self.sample_counts,
                out=np.full_like(self.counting_efficiency, np.nan),
                where=self.sample_counts > 0,
            )
        )

    @classmethod
    def read_root(cls, path):
        """Restore the same response model from the sampling ROOT export."""
        with uproot.open(path) as root:
            arrays = root["sampling"].arrays(library="np")
            edges = root["energy_bins"].arrays(library="np")
            metadata = json.loads(str(root["metadata"]))
        precision = metadata.pop("precision_settings", None)
        geometry = metadata.pop("geometry_psf", None)
        geometry_role = metadata.pop("geometry_psf_role", None)
        if not geometry or geometry_role not in ("physical", "transport"):
            raise ValueError("Sampling ROOT must contain its physical or transport PSF geometry")
        geometry = sphere_psf(PSF.read(StringIO(geometry)), transport=geometry_role == "transport")
        if not np.array_equal(edges["lower_MeV"], ENERGY_EDGES_MEV[:-1]) or not np.array_equal(
            edges["upper_MeV"], ENERGY_EDGES_MEV[1:]
        ):
            raise ValueError("Sampling ROOT energy grid differs from the AtRIS response grid")
        codes = arrays["pdg_codes"]
        shape = (len(codes), RESPONSE_ENERGY_BINS)
        if codes.ndim != 1 or len(set(codes)) != len(codes) or any(
            arrays[key].shape != shape for key in arrays if key != "pdg_codes"
        ):
            raise ValueError("Sampling ROOT must contain unique species and 650 bins per row")
        response = cls(codes, arrays["energy_fraction"], arrays["counting_efficiency"],
                       arrays["sample_counts"], arrays["fraction_standard_error"],
                       metadata["counting_threshold_MeV"], metadata, name=metadata["phantom"],
                       geometry=geometry,
                       precision_settings=DosePrecision.from_dict(precision) if precision else None)
        for key in ("radius_cm", "density_g_cm3", "mass_g", "atris_effective_area_cm2"):
            value = response.area_cm2 if key == "atris_effective_area_cm2" else getattr(response, key)
            if not np.isclose(value, metadata[key], rtol=ROOT_STATISTICS_RTOL, atol=0):
                raise ValueError(f"Sampling ROOT {key} differs from its PSF geometry")
        if not np.isclose(response.source_radius_cm, metadata["source"]["radius_cm"],
                          rtol=ROOT_STATISTICS_RTOL, atol=0):
            raise ValueError("Sampling ROOT source radius differs from its PSF geometry")
        for key in response._export_metadata(response.name):
            metadata.pop(key, None)
        counts = response.sample_counts
        detected = arrays["detected_counts"]
        if np.any(counts < 0) or np.any(detected < 0) or np.any(detected > counts):
            raise ValueError("Sampling ROOT counts are inconsistent")
        if not np.allclose(response.counting_efficiency[counts > 0],
                           detected[counts > 0] / counts[counts > 0], rtol=ROOT_STATISTICS_RTOL, atol=0):
            raise ValueError("Sampling ROOT counting efficiency differs from its counts")
        for name in ("fraction_variance", "counting_variance", "counting_standard_error"):
            if not np.allclose(arrays[name], getattr(response, name), rtol=ROOT_STATISTICS_RTOL,
                               atol=0, equal_nan=True):
                raise ValueError(f"Sampling ROOT {name} differs from its response statistics")
        return response

    def _write_sampling_root(self, path, metadata):
        arrays = dict(
            pdg_codes=np.asarray(self.pdg_codes, dtype=np.int64),
            energy_fraction=self.energy_fraction, counting_efficiency=self.counting_efficiency,
            sample_counts=np.asarray(self.sample_counts, dtype=np.int64),
            detected_counts=self.detected_counts,
            fraction_variance=self.fraction_variance,
            fraction_standard_error=self.fraction_standard_error,
            counting_variance=self.counting_variance,
            counting_standard_error=self.counting_standard_error,
        )
        for key in arrays.keys() - {"pdg_codes", "sample_counts", "detected_counts"}:
            arrays[key] = np.asarray(arrays[key], dtype=np.float64)
        # Readers see either the previous complete export or the new one.
        with TemporaryDirectory(prefix=".sampling-", dir=path.parent) as temporary:
            staged = Path(temporary) / path.name
            with uproot.recreate(staged) as root:
                root.mktree("sampling", {key: np.dtype((values.dtype, values.shape[1:]))
                             if values.ndim > 1 else values.dtype for key, values in arrays.items()})
                root["sampling"].extend(arrays)
                root.mktree("energy_bins", {"lower_MeV": "float64", "upper_MeV": "float64"})
                root["energy_bins"].extend(dict(lower_MeV=ENERGY_EDGES_MEV[:-1],
                                              upper_MeV=ENERGY_EDGES_MEV[1:]))
                root["metadata"] = json.dumps(metadata, allow_nan=False)
            staged.replace(path)

    def _export_metadata(self, name):
        stream = StringIO()
        self.geometry.save(stream)
        geometry = stream.getvalue()
        return {
            "schema": "atris.phantom.v1", "phantom": name,
            "validity": dict(geometry="spherical", scoring_detector_ids=[PHANTOM_DETECTOR_ID],
                termination_detector_ids=[0, 2], missing_species="unscored", energy_extrapolation=False),
            "radius_cm": self.radius_cm, "detector_inner_radius_cm": self.inner_radius_cm,
            "detector_layer_index": DETECTOR_LAYER, "density_g_cm3": self.density_g_cm3,
            "mass_g": self.mass_g, "projected_area_cm2": np.pi * self.source_radius_cm**2,
            "atris_effective_area_cm2": self.area_cm2,
            "effective_area_rule": "2*pi*source_radius_cm^2",
            "source": dict(shape="disk", radius_cm=self.source_radius_cm,
                centre_cm=[0, 0, -SOURCE_DISTANCE_RADII * self.source_radius_cm], direction=[0, 0, 1],
                energy_sampling="log_uniform"),
            "incident_energy": "total_kinetic_energy", "scored_deposit": "ionizing; primary_and_secondaries",
            "normalization": "per_incident_primary", "counting_threshold_MeV": self.threshold_MeV,
            "counting_definition": "P(W_ion > threshold)", "response_definition": "mean(W_ion/K)",
            "sampling_status": "partial" if np.any(self.sample_counts == 0) else "sampled",
            "sampling_file": f"{name}_sampling.root", "variance_ddof": 1,
            "uncertainty": "standard_error_of_mean", "geometry_psf": geometry,
            "geometry_psf_role": "physical",
            "precision_settings": asdict(self.precision_settings) if self.precision_settings else None,
        }

    def save(
        self, directory=".", *, name=None, allow_partial=True, **savetxt_kwargs
    ):
        """Save response/counting tables and sampling data; return their paths.

        Files are identified by the phantom name in the destination folder.
        The simulation selection in phantoms.txt is never created or changed.
        Return a tuple of Paths: response, counting, sampling ROOT, then the
        precision-state JSON if written. Existing named result files are replaced.
        Keyword arguments such as fmt are passed to numpy.savetxt for the two
        response matrices. Sampling information is retained in a ROOT file.
        Partial results are saved by default, with NaN marking unsampled bins.
        allow_partial=False requires every bin to have samples. Partial response
        tables remain identifiable as unfinished AtRIS simulation inputs.
        """
        directory = Path(directory)
        if name is None:
            name = self.name
        codes = np.asarray(self.pdg_codes)
        if (
            codes.ndim != 1
            or not len(codes)
            or codes[0] != PHOTON_PDG
            or len(set(codes)) != len(codes)
            or not np.issubdtype(codes.dtype, np.integer)
        ):
            raise ValueError("Use unique integer PDG codes with photons (22) first")
        shape = (len(codes), RESPONSE_ENERGY_BINS)
        arrays = (
            self.energy_fraction,
            self.counting_efficiency,
            self.sample_counts,
            self.fraction_standard_error,
        )
        if any(np.shape(a) != shape for a in arrays):
            raise ValueError("Each species must have 650 response bins")
        if not np.issubdtype(self.sample_counts.dtype, np.integer) or np.any(self.sample_counts < 0):
            raise ValueError("Sample counts must be nonnegative integers")
        if not allow_partial and np.any(self.sample_counts <= 0):
            raise ValueError(
                "Unsampled energy bins remain; run more phantom chunks"
            )
        if (
            not np.all(np.isfinite(self.energy_fraction[self.sample_counts > 0]))
            or np.any(self.energy_fraction < 0)
            or not np.all(np.isfinite(self.counting_efficiency[self.sample_counts > 0]))
            or np.any(self.counting_efficiency < 0)
            or np.any(self.counting_efficiency > 1)
        ):
            raise ValueError(
                "Responses must be finite, with counting efficiencies in [0, 1]"
            )
        if (
            not np.isfinite(self.mass_g)
            or self.mass_g <= 0
            or not np.isfinite(self.area_cm2)
            or self.area_cm2 <= 0
        ):
            raise ValueError("Phantom mass and area must be positive")
        if not name or Path(name).name != name or name in (".", "..") or any(c.isspace() for c in name):
            raise ValueError("Name must be a single filename component without whitespace")
        if {"header", "comments", "delimiter", "footer"} & savetxt_kwargs.keys():
            raise ValueError("The phantom header and whitespace layout are fixed")
        directory.mkdir(parents=True, exist_ok=True)
        metadata = self._export_metadata(name)
        metadata.update(
            {key: value for key, value in self.metadata.items() if key not in metadata}
        )
        table_metadata = {key: metadata[key] for key in (
            "phantom", "sampling_file", "sampling_status", "radius_cm", "density_g_cm3",
            "mass_g", "atris_effective_area_cm2", "counting_threshold_MeV",
            "response_definition", "counting_definition",
        )}
        response_path = directory / f"{name}_response.txt"
        counting_path = directory / f"{name}_counting.txt"
        sampling_path = directory / f"{name}_sampling.root"
        PhantomTable(
            codes, self.energy_fraction, metadata=table_metadata, allow_missing=allow_partial
        ).write(
            response_path,
            **savetxt_kwargs,
        )
        PhantomTable(
            codes,
            self.counting_efficiency,
            COUNTING_EFFICIENCY,
            table_metadata,
            allow_missing=allow_partial,
        ).write(
            counting_path,
            **savetxt_kwargs,
        )
        self._write_sampling_root(sampling_path, metadata)
        paths = [response_path, counting_path, sampling_path]
        if self.precision_settings is not None:
            settings = asdict(self.precision_settings)
            quality = self.precision()
            state_path = directory / f"{name}_sampling-state.json"
            with atomic_text_output(state_path) as output:
                output.write(json.dumps(dict(
                    total_bins=int(self.sample_counts.size),
                    sampled_bins=int(np.count_nonzero(self.sample_counts)),
                    resolved_bins=int(quality["resolved"].sum()),
                    passing_bins=int(quality["passed"].sum()),
                    precision_complete=bool(quality["passed"].all()),
                    **settings, counting_drives_sampling=False), indent=2, allow_nan=False) + "\n")
            paths.append(state_path)
        return tuple(paths)
