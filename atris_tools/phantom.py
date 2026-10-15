"""Prepare spherical phantom transport and merge its per-bin statistics.

The source irradiates the sphere's projected disk with a parallel beam.
Rotational symmetry makes this equivalent to isotropic irradiation of an
unshielded sphere. It is not an angular average for a nonspherical detector.
"""

from dataclasses import asdict, astuple, dataclass, field, fields
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import uproot

from .gather import atomic_text_output, chunk_name, read_chunk_plan
from .root_output import iterate_ntuple, read_ntuple
from .particles import ion_pdg, pdg_code
from .phantom_tables import PhantomTable, COUNTING_EFFICIENCY, ENERGY_EDGES_MEV
from .phantoms import RESPONSE_ENERGY_BINS
from .psf import (
    PSF, write_psf, load_psf, read_psf_header, DETECTOR_ID,
    INNER_RADIUS, OUTER_RADIUS, PHI_START, PHI_END, THETA_START, THETA_END,
    DENSITY, PRESSURE, STATE, FIRST_ELEMENT,
)
from .psf2gdml import psf2gdml

PHANTOM_DETECTOR_ID = 1
DETECTOR_LAYER = 0
PHOTON_PDG = pdg_code("photon")
RESPONSE_ENERGY_EDGES_MEV = ENERGY_EDGES_MEV
CM_PER_KM = 1e5
JOULES_PER_MEV = 1.602176634e-13
KG_PER_GRAM = 1e-3
SPHERE_ANGLE_TOLERANCE = 1e-10
ROOT_STATISTICS_RTOL = 1e-14
ROOT_ENERGY_GRID_RTOL = 1e-12
VACUUM_DENSITY_G_CM3 = 1e-25
# Distances are multiples of the sphere radius. The beam starts just outside
# the sphere; two enclosing shells terminate escaped tracks in detectors 0/2.
SOURCE_DISTANCE_RADII = 1.1
TRANSPORT_INNER_RADII = (0, 2, 2.2)
TRANSPORT_OUTER_RADII = (1, 2.1, 2.3)
TRANSPORT_DETECTOR_IDS = (PHANTOM_DETECTOR_ID, 0, 2)
WORLD_MARGIN_RADII = 1.7
CHUNK_SEED_MIN = 31
CHUNK_SEED_MAX_EXCLUSIVE = 1_000_000


def sphere_psf(path, *, transport=False):
    """Read spherical physical layers, preserving the supplied PSF materials."""
    psf = path if isinstance(path, PSF) else PSF.read(path)
    if transport:
        layers = psf.layers[~np.isin(psf.layers[:, DETECTOR_ID], TRANSPORT_DETECTOR_IDS[1:])]
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


@dataclass
class PhantomStatistics:
    """Mergeable per-energy sampling statistics for one incident species.

    Central squared deviations avoid cancellation when nearly every primary
    deposits the same fraction. Zero-count bins are marked NaN on export.
    """

    sample_counts: np.ndarray
    mean_fraction: np.ndarray
    squared_deviations: np.ndarray
    detected_counts: np.ndarray

    def __str__(self):
        return "\n".join([
            "Phantom statistics",
            f"Primaries: {self.sample_counts.sum():,}",
            f"Sampled energy bins: {np.count_nonzero(self.sample_counts):,}/{self.sample_counts.size:,}",
            f"Bins with at least two primaries: {np.count_nonzero(self.sample_counts > 1):,}",
            f"Counted primaries: {self.detected_counts.sum():,}",
        ])

    @classmethod
    def empty(cls):
        return cls(
            np.zeros(RESPONSE_ENERGY_BINS, dtype=int),
            np.zeros(RESPONSE_ENERGY_BINS),
            np.zeros(RESPONSE_ENERGY_BINS),
            np.zeros(RESPONSE_ENERGY_BINS, dtype=int),
        )

    @classmethod
    def from_events(cls, events, threshold_MeV=0.0):
        incident = events.incident_energy_MeV
        if np.any(incident < RESPONSE_ENERGY_EDGES_MEV[0]) or np.any(
            incident >= RESPONSE_ENERGY_EDGES_MEV[-1]
        ):
            raise ValueError(
                "Phantom energies must lie inside the AtRIS response grid"
            )
        fraction = events.ionizing_energy_MeV / incident
        count = np.histogram(incident, RESPONSE_ENERGY_EDGES_MEV)[0]
        total = np.histogram(incident, RESPONSE_ENERGY_EDGES_MEV, weights=fraction)[0]
        mean = np.divide(
            total, count, out=np.zeros(RESPONSE_ENERGY_BINS), where=count > 0
        )
        bins = np.searchsorted(RESPONSE_ENERGY_EDGES_MEV, incident, side="right") - 1
        deviations = np.bincount(
            bins, weights=(fraction - mean[bins]) ** 2, minlength=RESPONSE_ENERGY_BINS
        )
        detected = np.histogram(
            incident[events.ionizing_energy_MeV > threshold_MeV],
            RESPONSE_ENERGY_EDGES_MEV,
        )[0]
        return cls(count, mean, deviations, detected)

    def __iadd__(self, other):
        """Combine independent chunks using the parallel central-moment formula."""
        count = self.sample_counts + other.sample_counts
        delta = other.mean_fraction - self.mean_fraction
        weight = np.divide(
            other.sample_counts,
            count,
            out=np.zeros(RESPONSE_ENERGY_BINS),
            where=count > 0,
        )
        self.squared_deviations += (
            other.squared_deviations + delta**2 * self.sample_counts * weight
        )
        self.mean_fraction += delta * weight
        self.sample_counts = count
        self.detected_counts += other.detected_counts
        return self


def _read_dose_settings(settings):
    """Read the previous on-disk tolerance spelling into the current model."""
    settings = dict(settings)
    if "relative_tolerance" in settings:
        value = settings.pop("relative_tolerance")
        if "relative_dose_tolerance" in settings and settings["relative_dose_tolerance"] != value:
            raise ValueError("Conflicting relative dose tolerances")
        settings["relative_dose_tolerance"] = value
    return settings


@dataclass(frozen=True)
class DosePrecision:
    relative_dose_tolerance: float
    absolute_dose_tolerance_Gy: float
    confidence_factor: float

    def __post_init__(self):
        if not all(np.isfinite(value) and value > 0 for value in (
            self.relative_dose_tolerance, self.absolute_dose_tolerance_Gy, self.confidence_factor
        )):
            raise ValueError("Dose precision settings must be finite and positive")


@dataclass(frozen=True)
class SamplingSettings:
    stem: str
    pdg_codes: list[int]
    pilot_events: int | dict[str, int]
    production_cut_mm: float
    seed: int
    physics_list: str
    psf_sha256: str
    precision: DosePrecision
    tracking_floor_eV: float | None = None

    @classmethod
    def from_dict(cls, data):
        data = _read_dose_settings(data)
        precision = DosePrecision(**{item.name: data.pop(item.name) for item in fields(DosePrecision)})
        return cls(**data, precision=precision)

    def to_dict(self):
        data = asdict(self)
        data.update(data.pop("precision"))
        return data


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

    @classmethod
    def gather(cls, name=None, *, directory="."):
        """Gather a named phantom's completed chunks from a sampling folder.

        The name is checked against the folder's saved sampling settings.
        Omitting it uses the saved name; directory defaults to the current folder.
        """
        from .phantom_builder import PhantomBuilder

        builder = PhantomBuilder.open(directory)
        settings = builder.settings
        if name is not None and name != settings.stem:
            raise ValueError(f"Sampling folder contains phantom {settings.stem!r}, not {name!r}")
        statistics = {code: PhantomStatistics.empty() for code in settings.pdg_codes}
        versions = set()
        for batch in builder._batches():
            chunk = builder._chunk(batch)
            if chunk.with_suffix(".COMPLETE").is_file():
                metadata = read_ntuple(chunk.with_suffix(".root"), "metadata",
                                       ("atris_version", "physics_list"))
                if set(metadata["physics_list"]) != {settings.physics_list}:
                    raise ValueError("Completed chunk physics list differs from the prepared build")
                versions.update(metadata["atris_version"])
                statistics[batch["pdg"]] += read_phantom_statistics(chunk.with_suffix(".root"))
        return cls.from_statistics(
            statistics, geometry=builder.geometry,
            name=settings.stem,
            precision_settings=settings.precision,
            metadata=dict(physics_list=settings.physics_list,
                          production_cut_mm=settings.production_cut_mm,
                          atris_version=", ".join(sorted(versions)) or "not recorded",
                          generator="atris_tools.phantom_builder", psf_sha256=settings.psf_sha256,
                          sampling_settings=settings.to_dict()),
        )

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
        centres = (RESPONSE_ENERGY_EDGES_MEV[:-1] + RESPONSE_ENERGY_EDGES_MEV[1:]) / 2
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
        if not np.array_equal(edges["lower_MeV"], RESPONSE_ENERGY_EDGES_MEV[:-1]) or not np.array_equal(
            edges["upper_MeV"], RESPONSE_ENERGY_EDGES_MEV[1:]
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
                       precision_settings=DosePrecision(**_read_dose_settings(precision)) if precision else None)
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
                root["energy_bins"].extend(dict(lower_MeV=RESPONSE_ENERGY_EDGES_MEV[:-1],
                                              upper_MeV=RESPONSE_ENERGY_EDGES_MEV[1:]))
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


@dataclass
class PhantomEvents:
    """One entry per incident primary, including events with zero deposition."""

    incident_energy_MeV: np.ndarray
    deposited_energy_MeV: np.ndarray
    ionizing_energy_MeV: np.ndarray

    def __str__(self):
        lines = [f"Phantom events: {self.incident_energy_MeV.size:,} primaries"]
        if self.incident_energy_MeV.size:
            lines.append(f"Incident kinetic energy: {self.incident_energy_MeV.min():g} "
                         f"to {self.incident_energy_MeV.max():g} MeV")
        lines.append(f"Positive ionizing deposits: {np.count_nonzero(self.ionizing_energy_MeV > 0):,}")
        return "\n".join(lines)


def prepare_phantom_batch(
    run_directory,
    energy_edges_MeV,
    *,
    psf_path,
    particle="proton",
    events_per_chunk=4000,
    chunks=3,
    seed=314159,
    production_cut_mm=0.1,
    tracking_floor_eV=None,
    ion=None,
):
    """Write GDML, a log-uniform source macro, and an atris-run chunk plan.

    The directory must already exist. Repeating the same preparation is a
    no-op. Increasing chunks appends new seeds without changing existing jobs;
    changing the physical setup requires a directory without an existing plan.
    This preparation does not load an existing response table.
    Named particles include light nuclei (deuteron, triton, He3, alpha).
    For other ground-state nuclei, use particle="ion" and a dictionary with
    integer Z, A, and charge (in elementary-charge units).
    """
    directory = Path(run_directory)
    physical = sphere_psf(psf_path)
    radius_cm = float(physical.layers[-1, OUTER_RADIUS] * CM_PER_KM)
    edges = np.asarray(energy_edges_MeV, dtype=float)
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or edges[0] <= 0
        or np.any(np.diff(edges) <= 0)
    ):
        raise ValueError("Energy edges must be finite, positive, and increasing")
    if not all(
        np.isfinite(x) and x > 0 for x in (radius_cm, production_cut_mm)
    ):
        raise ValueError("Radius and production cut must be positive")
    if chunks < 1 or events_per_chunk < 1:
        raise ValueError("Chunks and events per chunk must be positive")
    if tracking_floor_eV is not None and (
        not np.isfinite(tracking_floor_eV) or tracking_floor_eV < 0
    ):
        raise ValueError("The tracking floor must be finite and nonnegative")
    if not particle or any(character.isspace() for character in particle):
        raise ValueError("Use one Geant4 particle name, such as proton or gamma")
    source_commands = f"/gps/particle {particle}\n"
    if particle == "ion":
        if ion is None or set(ion) != {"Z", "A", "charge"}:
            raise ValueError("For particle='ion', supply ion with Z, A, and charge")
        if any(not isinstance(value, (int, np.integer)) for value in ion.values()):
            raise ValueError("Ion Z, A, and charge must be integers")
        ion = {key: int(value) for key, value in ion.items()}
        ion_pdg(ion["Z"], ion["A"])
        if not 0 <= ion["charge"] <= ion["Z"]:
            raise ValueError("Use 0 <= charge <= Z")
        source_commands += f"/gps/ion {ion['Z']} {ion['A']} {ion['charge']} 0\n"
    elif ion is not None:
        raise ValueError("Ion properties require particle='ion'")
    if (directory / "phantoms.txt").exists():
        raise ValueError("Use a phantom directory without phantoms.txt")
    config = dict(
        particle=particle,
        events_per_chunk=events_per_chunk,
        chunks=chunks,
        seed=seed,
        production_cut_mm=production_cut_mm,
        energy_edges_MeV=edges.tolist(),
    )
    if ion is not None:
        config["ion"] = ion
    tracking_commands = ""
    if tracking_floor_eV is not None:
        config["tracking_floor_eV"] = tracking_floor_eV
        tracking_commands = (
            f"/process/em/lowestElectronEnergy {tracking_floor_eV:.17e} eV\n"
            f"/process/em/lowestMuHadEnergy {tracking_floor_eV:.17e} eV\n"
        )
    config_path = directory / "phantom-run.json"
    if (directory / "chunks.txt").exists():
        if config_path.exists():
            previous = json.loads(config_path.read_text())
            requested = config.copy()
            previous.pop("chunks")
            requested.pop("chunks")
            retained = sphere_psf(directory / "phantom.psf", transport=True)
            expected = physical.layers.copy()
            expected[:, DETECTOR_ID] = -1
            expected[DETECTOR_LAYER, DETECTOR_ID] = PHANTOM_DETECTOR_ID
            same_geometry = retained.materials == physical.materials and np.array_equal(retained.layers, expected)
            if previous == requested and same_geometry:
                entries = read_chunk_plan(directory)
                if chunks > len(entries):
                    _write_chunk_plan(directory, chunks, seed, entries)
                    config_path.write_text(json.dumps(config, indent=2) + "\n")
                return
        raise FileExistsError(
            "A different phantom already exists in this directory"
        )

    radius_km = radius_cm / CM_PER_KM
    # The physical layer is unchanged; IDs 0/2 are vacuum termination shells.
    layers = np.concatenate((physical.layers.copy(), np.repeat(physical.layers[-1:], 2, axis=0)))
    layers[:-2, DETECTOR_ID] = -1
    layers[DETECTOR_LAYER, DETECTOR_ID] = PHANTOM_DETECTOR_ID
    layers[-2:, INNER_RADIUS] = np.array(TRANSPORT_INNER_RADII[1:]) * radius_km
    layers[-2:, OUTER_RADIUS] = np.array(TRANSPORT_OUTER_RADII[1:]) * radius_km
    layers[-2:, DETECTOR_ID] = TRANSPORT_DETECTOR_IDS[1:]
    layers[-2:, DENSITY] = VACUUM_DENSITY_G_CM3
    layers[-2:, PRESSURE] = 0
    layers[-2:, STATE] = 0
    layers[-2:, FIRST_ELEMENT:] = 0
    layers[-2:, FIRST_ELEMENT] = 1
    geometry = PSF.from_layers(layers, physical.materials)
    write_psf(directory / "phantom.psf", geometry)
    psf2gdml(directory / "phantom.psf", directory / "phantom.gdml",
             world_margin_km=WORLD_MARGIN_RADII * radius_km)
    # The source range may cover only part of the shared response grid.
    np.savetxt(directory / "phantom.bins", RESPONSE_ENERGY_EDGES_MEV)
    macro = f"""{tracking_commands}/run/setCut {production_cut_mm:.17e} mm
/run/initialize
{source_commands}/gps/pos/type Plane
/gps/pos/shape Circle
/gps/pos/centre 0 0 {-SOURCE_DISTANCE_RADII * radius_cm:.17e} cm
/gps/pos/radius {radius_cm:.17e} cm
/gps/direction 0 0 1
/gps/ene/type Pow
/gps/ene/alpha -1
/gps/ene/min {edges[0]:.17e} MeV
/gps/ene/max {edges[-1]:.17e} MeV
/run/beamOn {events_per_chunk}
"""
    (directory / "phantom.chunk.mac").write_text(macro)
    (directory / "chunks").mkdir(exist_ok=True)
    _write_chunk_plan(directory, chunks, seed)
    config_path.write_text(json.dumps(config, indent=2) + "\n")


def _write_chunk_plan(directory, chunks, seed, entries=()):
    rng = np.random.default_rng(seed)
    previous = {(int(a), int(b)) for _, a, b in entries}
    seeds = set(previous)
    while len(seeds) < chunks:
        seeds.add(tuple(rng.integers(CHUNK_SEED_MIN, CHUNK_SEED_MAX_EXCLUSIVE, size=2)))
    plan = "".join(f"{name} {a} {b}\n" for name, a, b in entries)
    plan += "".join(
        f"phantom {a:06d} {b:06d}\n" for a, b in sorted(seeds - previous)
    )
    with atomic_text_output(directory / "chunks.txt") as output:
        output.write(plan)


def read_phantom_statistics(path, threshold_MeV=0.0):
    """Read compact native statistics, or reduce retained older event records.

    Native counting uses positive ionizing deposition (threshold zero).
    Changing that threshold requires older files with individual event records.
    ROOT's per-bin sum(w^2) is a raw second moment, not a sample variance.
    """
    with uproot.open(path) as root:
        if "phantom_events" in root or "steps" in root:
            return PhantomStatistics.from_events(
                read_phantom_events(path), threshold_MeV
            )
        if threshold_MeV != 0:
            raise ValueError("Compact phantom statistics use a zero counting threshold")
        primary = root["h1.1"]
        fraction = root["h2.fraction"]
        edges = primary.axis().edges()
        if edges.shape != RESPONSE_ENERGY_EDGES_MEV.shape or not np.allclose(
            edges, RESPONSE_ENERGY_EDGES_MEV, rtol=ROOT_ENERGY_GRID_RTOL, atol=0
        ):
            raise ValueError(
                "Compact phantom histograms must use the AtRIS response grid"
            )
        if len(fraction.member("fSumw2")) == 0:
            raise ValueError("Phantom histogram is missing per-bin squared sums")
        detector_bin = (
            np.searchsorted(fraction.axes[1].edges(), PHANTOM_DETECTOR_ID, side="right")
            - 1
        )
        counts = primary.values().astype(np.int64)
        totals = fraction.values()[:, detector_bin]
        squares = fraction.variances()[:, detector_bin]
        means = np.divide(totals, counts, out=np.zeros_like(totals), where=counts > 0)
        # Raw second-moment subtraction can round slightly below zero.
        deviations = np.maximum(0, squares - totals * means)
        detected = root["h2.detected"].values()[:, detector_bin].astype(np.int64)
    return PhantomStatistics(counts, means, deviations, detected)


def read_phantom_events(path):
    """Read one native phantom chunk, or sum its older shower step records."""
    with uproot.open(path) as root:
        if "phantom_events" in root:
            arrays = root["phantom_events"].arrays(library="np")
            # Older compacted shower files contain only scored-volume rows;
            # native files identify detector volumes and can contain others.
            detector = (
                arrays["detector_id"] == PHANTOM_DETECTOR_ID
                if "detector_id" in arrays
                else slice(None)
            )
            return PhantomEvents(
                *(arrays[name][detector] for name in PhantomEvents.__dataclass_fields__)
            )
        if "steps" not in root:
            raise ValueError(
                "This chunk stores per-bin statistics; use read_phantom_statistics"
            )
        event_count = int(root["h1.1"].member("fEntries"))
    energy = np.zeros(event_count)
    deposited = np.zeros(event_count)
    ionizing = np.zeros(event_count)
    fields = (
        "event_id",
        "detector_id",
        "primary_energy_MeV",
        "energy_deposit_MeV",
        "nonionizing_energy_deposit_MeV",
    )
    for steps in iterate_ntuple(path, "steps", fields):
        event_id = steps["event_id"]
        if np.any(event_id < 0) or np.any(event_id >= event_count):
            raise ValueError(f"Invalid event IDs in {path}")
        np.maximum.at(energy, event_id, steps["primary_energy_MeV"])
        detector = steps["detector_id"] == PHANTOM_DETECTOR_ID
        event_id = event_id[detector]
        total = steps["energy_deposit_MeV"][detector]
        nonionizing = steps["nonionizing_energy_deposit_MeV"][detector]
        deposited += np.bincount(event_id, weights=total, minlength=event_count)
        ionizing += np.bincount(
            event_id, weights=total - nonionizing, minlength=event_count
        )
    if np.any(energy <= 0):
        raise ValueError(
            f"Missing primary energies in {path}; use phantom or shower output"
        )
    return PhantomEvents(energy, deposited, ionizing)


def compact_phantom_chunk(path):
    """Replace detailed track records with verified per-primary energy sums.

    Preserve histograms and metadata. The steps and interfaces ntuples are
    deliberately discarded: they are not needed to regenerate response tables
    from the stored primary energies, total deposits and ionizing deposits.
    The original file remains intact until the compact file has been reread
    and its event arrays have been compared exactly with the original sums.
    """
    path = Path(path)
    with uproot.open(path) as root:
        if "phantom_events" in root:
            return
    events = read_phantom_events(path)
    temporary = path.with_suffix(".compact.root")
    with uproot.open(path) as source, uproot.recreate(temporary) as destination:
        # Bulk-copy histogram bytes, preserving their Geant4 ROOT streamers,
        # annotations and uncertainty arrays without reinterpretation.
        destination.copy_from(
            source,
            filter_name=lambda name: name not in ("steps", "interfaces"),
            filter_classname=lambda classname: classname != "TTree",
        )
        for name, classname in source.classnames(cycle=False).items():
            if classname == "TTree" and name not in ("steps", "interfaces"):
                destination.mktree(name, source[name].arrays(library="ak", how=dict))
        destination.mktree(
            "phantom_events",
            {
                name: getattr(events, name)
                for name in PhantomEvents.__dataclass_fields__
            },
        )
        destination.mktree(
            "phantom_compaction",
            {
                "discarded_ntuples": ["steps, interfaces"],
                "retained_events": [
                    "one row per incident primary, including zero-deposit events"
                ],
            },
        )
    reread = read_phantom_events(temporary)
    for name in PhantomEvents.__dataclass_fields__:
        np.testing.assert_array_equal(getattr(reread, name), getattr(events, name))
    temporary.replace(path)


def gather_phantom_events(run_directory):
    """Combine completed phantom chunks, keeping event IDs local to each.

    Read raw or compacted chunk ROOT files when event-level post-processing
    requires the per-primary records.
    """
    directory = Path(run_directory)
    results = []
    for entry in read_chunk_plan(directory):
        name = chunk_name(entry)
        if (directory / "chunks" / (name + ".COMPLETE")).is_file():
            results.append(read_phantom_events(directory / "chunks" / (name + ".root")))
    if not results:
        raise ValueError("No completed phantom chunks")
    return PhantomEvents(
        *(
            np.concatenate([getattr(result, field) for result in results])
            for field in PhantomEvents.__dataclass_fields__
        )
    )
