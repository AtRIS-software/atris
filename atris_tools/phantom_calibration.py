"""Prepare a water-sphere calibration and merge its per-bin statistics.

The calibration irradiates the sphere's projected disk with a parallel beam.
Rotational symmetry makes this equivalent to isotropic irradiation of an
unshielded sphere. It is not an angular average for a nonspherical detector.
"""

from dataclasses import dataclass, field
from importlib.resources import files
import hashlib
import json
from pathlib import Path

import numpy as np
import uproot

from .gather import atomic_text_output, chunk_name, read_chunk_plan
from .root_output import iterate_ntuple, read_ntuple
from .particles import ion_pdg, pdg_code
from .phantom_tables import PhantomTable, COUNTING_EFFICIENCY, ENERGY_EDGES_MEV
from .phantoms import RESPONSE_ENERGY_BINS

WATER_DETECTOR_ID = 1
RESPONSE_ENERGY_EDGES_MEV = ENERGY_EDGES_MEV


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
                "Calibration energies must lie inside the AtRIS response grid"
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


@dataclass
class PhantomResponse:
    """Sampled water-sphere responses on the AtRIS grid, one row per PDG code.

    Energy fractions are per intercepted primary, including its secondaries.
    Missing samples remain NaN and cannot be exported as measured zeroes.
    """

    pdg_codes: np.ndarray
    energy_fraction: np.ndarray
    counting_efficiency: np.ndarray
    sample_counts: np.ndarray
    fraction_standard_error: np.ndarray
    radius_cm: float
    density_g_cm3: float
    threshold_MeV: float
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_statistics(
        cls, statistics, *, radius_cm, density_g_cm3, threshold_MeV=0.0, metadata=None
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
            radius_cm,
            density_g_cm3,
            threshold_MeV,
            metadata or {},
        )

    @property
    def mass_g(self):
        return 4 / 3 * np.pi * self.radius_cm**3 * self.density_g_cm3

    @property
    def area_cm2(self):
        """Area for AtRIS's two-direction interface-crossing normalization."""
        return 2 * np.pi * self.radius_cm**2

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

    def write(
        self, directory, *, stem="water-sphere", allow_partial=False, **savetxt_kwargs
    ):
        """Write loadable response/counting tables and a one-phantom selection.

        Use a dedicated export directory: phantoms.txt selects just this phantom.
        Keyword arguments such as fmt are passed to numpy.savetxt for the two
        response matrices. Sampling information is retained in a separate NPZ.
        Live builds may use allow_partial=True: NaN marks unsampled bins, so
        those tables are not yet loadable as AtRIS simulation inputs.
        """
        directory = Path(directory)
        codes = np.asarray(self.pdg_codes)
        if (
            codes.ndim != 1
            or not len(codes)
            or codes[0] != 22
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
        if not allow_partial and np.any(self.sample_counts <= 0):
            raise ValueError(
                "Unsampled energy bins remain; run more calibration chunks"
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
        if not stem or Path(stem).name != stem or any(c.isspace() for c in stem):
            raise ValueError("Use a filename stem without directories or whitespace")
        if {"header", "comments", "delimiter", "footer"} & savetxt_kwargs.keys():
            raise ValueError("The phantom header and whitespace layout are fixed")
        directory.mkdir(parents=True, exist_ok=True)
        metadata = {
            "phantom": stem,
            "geometry": "homogeneous, unshielded sphere in vacuum",
            "material": "liquid water; H2O (2 H atoms per O atom)",
            "material_atomic_masses_g_mol": "H=1.00794; O=15.9994",
            "material_temperature_pressure": "not explicitly set in GDML; Geant4 defaults",
            "mean_excitation_energy": "not overridden; determined by Geant4",
            "radius_cm": self.radius_cm,
            "diameter_cm": 2 * self.radius_cm,
            "density_g_cm3": self.density_g_cm3,
            "mass_g": self.mass_g,
            "projected_area_cm2": np.pi * self.radius_cm**2,
            "surface_area_cm2": 4 * np.pi * self.radius_cm**2,
            "atris_effective_area_cm2": self.area_cm2,
            "atris_effective_area_convention": "2 pi r^2; isotropic two-direction interface crossings, not geometric area",
            "geometry_recipe": "atris_tools/data/water-phantom.gdml; generated GDML retained in the calibration directories",
            "source_position_cm": f"uniform disk of radius {self.radius_cm:g} at z={-1.1 * self.radius_cm:g}",
            "source_direction": "parallel beam along +z; sphere symmetry makes orientation immaterial",
            "incident_energy_sampling": "log-uniform total kinetic energy",
            "energy_deposit": "ionizing deposit = total deposit minus nonionizing deposit; all secondary tracks included",
            "normalization": "per incident primary intercepted by the sphere; zero-deposit events included",
            "counting_threshold_MeV": self.threshold_MeV,
            "counting_definition": "fraction of primaries with ionizing deposit strictly greater than counting_threshold_MeV",
            "response_threshold": "none; counting threshold does not gate the energy response",
            "response_definition": "mean of ionizing deposited energy / actual incident kinetic energy within each bin",
            "sampling_status": (
                "incomplete; NaN marks unsampled bins; not yet loadable in AtRIS"
                if np.any(self.sample_counts == 0)
                else "all energy bins sampled"
            ),
            "sampling_file": f"{stem}_sampling.npz",
            "sampling_arrays": "pdg_codes, energy_edges_MeV, sample_counts, detected_counts, fraction_variance, fraction_standard_error, counting_variance, counting_standard_error; same particle/bin order as tables",
            "uncertainty": "fraction_standard_error is the standard error of the mean energy fraction, not event standard deviation; NaN for fewer than 2 samples",
            "variance_file": f"{stem}_variance.txt",
            "variance_definition": "sample variance of per-primary ionizing energy fractions, with denominator N-1; dimensionless squared; NaN for fewer than 2 samples",
            "counting_uncertainty": "counting_standard_error is sqrt(counting_variance / N); zero estimated error does not exclude rare events; use detected_counts and sample_counts for binomial intervals",
        }
        metadata.update(
            {key: value for key, value in self.metadata.items() if key not in metadata}
        )
        for code, count in zip(codes, self.sample_counts):
            metadata[f"pdg_{code}_sample_counts"] = (
                f"total={int(count.sum())}; per-bin minimum={int(count.min())}, maximum={int(count.max())}"
            )
        PhantomTable(
            codes, self.energy_fraction, metadata=metadata, allow_missing=allow_partial
        ).write(
            directory / f"{stem}_response.txt",
            **savetxt_kwargs,
        )
        PhantomTable(
            codes,
            self.counting_efficiency,
            COUNTING_EFFICIENCY,
            metadata,
            allow_missing=allow_partial,
        ).write(
            directory / f"{stem}_counting.txt",
            **savetxt_kwargs,
        )
        np.savetxt(
            directory / f"{stem}_variance.txt",
            self.fraction_variance,
            header=(
                "# Sample variance of per-primary ionizing deposited-energy fractions.\n"
                "# This is not the standard error of the mean response.\n"
                "# definition: sum((fraction - mean)^2) / (N - 1)\n"
                "# coefficient_unit: 1 (dimensionless squared)\n"
                "# missing_statistics: NaN where N < 2\n"
                f"# energy_edges_file: {stem}_sampling.npz; energy_edges_MeV\n"
                "# layout: PDG header followed by one row per species\n"
                + " ".join(map(str, codes))
            ),
            comments="",
            **savetxt_kwargs,
        )
        (directory / "phantoms.txt").write_text(
            "# ID stem mass_g area_cm2\n"
            f"0 {stem} {self.mass_g:.17e} {self.area_cm2:.17e}\n"
        )
        np.savez_compressed(
            directory / f"{stem}_sampling.npz",
            pdg_codes=codes,
            energy_edges_MeV=RESPONSE_ENERGY_EDGES_MEV,
            sample_counts=self.sample_counts,
            detected_counts=np.rint(
                np.where(
                    self.sample_counts > 0,
                    self.counting_efficiency * self.sample_counts,
                    0,
                )
            ).astype(int),
            fraction_variance=self.fraction_variance,
            fraction_standard_error=self.fraction_standard_error,
            counting_variance=self.counting_variance,
            counting_standard_error=self.counting_standard_error,
        )
        metadata.update(
            radius_cm=self.radius_cm,
            density_g_cm3=self.density_g_cm3,
            counting_threshold_MeV=self.threshold_MeV,
            pdg_codes=codes.tolist(),
            response_quantity="mean ionizing energy fraction",
            area_convention="2 pi r^2; isotropic two-direction interface crossings",
            missing_species="not scored",
        )
        (directory / f"{stem}_calibration.json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )


def calibrate_water_phantom(runs_by_pdg, *, threshold_MeV=0.0):
    """Read completed runs and estimate responses on the fixed AtRIS grid.

    runs_by_pdg maps each particle's PDG code to its calibration directory.
    All runs must use the same sphere and production cut. Rows retain the
    mapping's order; place photons first when writing for the current reader.
    """
    if not np.isfinite(threshold_MeV) or threshold_MeV < 0:
        raise ValueError("The counting threshold must be finite and nonnegative")
    if not runs_by_pdg:
        raise ValueError("Supply at least one calibration run")
    geometry = None
    statistics = {}
    metadata = {}
    physics_lists, atris_versions, geant4_versions = set(), set(), set()
    for pdg, directory in runs_by_pdg.items():
        directory = Path(directory)
        config = json.loads((directory / "water-phantom.json").read_text())
        if "particle" in config:
            source_pdg = (
                ion_pdg(config["ion"]["Z"], config["ion"]["A"])
                if config["particle"] == "ion"
                else pdg_code(config["particle"])
            )
            if pdg != source_pdg:
                raise ValueError(f"PDG {pdg} does not match source PDG {source_pdg}")
        settings = tuple(
            config.get(key)
            for key in (
                "radius_cm",
                "density_g_cm3",
                "production_cut_mm",
                "tracking_floor_eV",
            )
        )
        if geometry is not None and settings != geometry:
            raise ValueError(
                "Calibration runs must use the same sphere and production cut"
            )
        geometry = settings
        metadata[f"pdg_{pdg}_source"] = config.get("particle", "not recorded")
        if "ion" in config:
            metadata[f"pdg_{pdg}_ion"] = (
                f"Z={config['ion']['Z']}, A={config['ion']['A']}, charge={config['ion']['charge']} e; ground state"
            )
        source_edges = config.get("energy_edges_MeV")
        metadata[f"pdg_{pdg}_source_energy_range_MeV"] = (
            f"{source_edges[0]:g} to {source_edges[-1]:g}"
            if source_edges
            else "not recorded"
        )
        completed = []
        statistics[pdg] = PhantomStatistics.empty()
        if (directory / "chunks.txt").exists():
            for entry in read_chunk_plan(directory):
                name = chunk_name(entry)
                if not (directory / "chunks" / (name + ".COMPLETE")).is_file():
                    continue
                completed.append(f"{entry[1]} {entry[2]}")
                statistics[pdg] += read_phantom_statistics(
                    directory / "chunks" / (name + ".root"), threshold_MeV
                )
                records = read_ntuple(
                    directory / "chunks" / (name + ".root"),
                    "metadata",
                    ("atris_version", "physics_list"),
                )
                atris_versions.update(records["atris_version"])
                physics_lists.update(records["physics_list"])
                log = directory / "chunks" / (name + ".log")
                if log.exists():
                    geant4_versions.update(
                        line.partition("Geant4 version Name:")[2].strip()
                        for line in log.read_text().splitlines()
                        if "Geant4 version Name:" in line
                    )
        metadata[f"pdg_{pdg}_completed_chunk_seed_pairs"] = (
            "; ".join(completed) or "not recorded"
        )
        if not completed:
            raise ValueError(f"No completed calibration chunks in {directory}")
    metadata.update(
        production_cut_mm=geometry[2] if geometry[2] is not None else "not recorded",
        electron_muon_hadron_tracking_floor_eV=(
            geometry[3] if geometry[3] is not None else "Geant4 defaults; no override"
        ),
        physics_list=", ".join(sorted(physics_lists)) or "not recorded",
        atris_version=", ".join(sorted(atris_versions)) or "not recorded",
        geant4_version=", ".join(sorted(geant4_versions)) or "not recorded",
        generator="atris_tools.phantom_calibration; prepare_water_phantom / calibrate_water_phantom",
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    return PhantomResponse.from_statistics(
        statistics,
        radius_cm=geometry[0],
        density_g_cm3=geometry[1],
        threshold_MeV=threshold_MeV,
        metadata=metadata,
    )


@dataclass
class PhantomEvents:
    """One entry per incident primary, including events with zero deposition."""

    incident_energy_MeV: np.ndarray
    deposited_energy_MeV: np.ndarray
    ionizing_energy_MeV: np.ndarray


def prepare_water_phantom(
    run_directory,
    energy_edges_MeV,
    *,
    radius_cm=15.0,
    density_g_cm3=0.997,
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
    No previously calculated phantom response is loaded during calibration.
    Named particles include light nuclei (deuteron, triton, He3, alpha).
    For other ground-state nuclei, use particle="ion" and a dictionary with
    integer Z, A, and charge (in elementary-charge units).
    """
    directory = Path(run_directory)
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
        np.isfinite(x) and x > 0 for x in (radius_cm, density_g_cm3, production_cut_mm)
    ):
        raise ValueError("Radius, density, and production cut must be positive")
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
        raise ValueError("Use a calibration directory without phantoms.txt")
    config = dict(
        radius_cm=radius_cm,
        density_g_cm3=density_g_cm3,
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
    config_path = directory / "water-phantom.json"
    if (directory / "chunks.txt").exists():
        if config_path.exists():
            previous = json.loads(config_path.read_text())
            requested = config.copy()
            previous.pop("chunks")
            requested.pop("chunks")
            if previous == requested:
                entries = read_chunk_plan(directory)
                if chunks > len(entries):
                    _write_chunk_plan(directory, chunks, seed, entries)
                    config_path.write_text(json.dumps(config, indent=2) + "\n")
                return
        raise FileExistsError(
            "A different calibration already exists in this directory"
        )

    template = files("atris_tools").joinpath("data/water-phantom.gdml").read_text()
    geometry = template.format(
        radius=radius_cm,
        density=density_g_cm3,
        world_size=8 * radius_cm,
        escape_inner=2 * radius_cm,
        escape_outer=2.1 * radius_cm,
        guard_inner=2.2 * radius_cm,
        guard_outer=2.3 * radius_cm,
    )
    (directory / "calibration.gdml").write_text(geometry)
    # The source range may cover only part of the shared response grid.
    np.savetxt(directory / "calibration.bins", RESPONSE_ENERGY_EDGES_MEV)
    macro = f"""{tracking_commands}/run/setCut {production_cut_mm:.17e} mm
/run/initialize
{source_commands}/gps/pos/type Plane
/gps/pos/shape Circle
/gps/pos/centre 0 0 {-1.1 * radius_cm:.17e} cm
/gps/pos/radius {radius_cm:.17e} cm
/gps/direction 0 0 1
/gps/ene/type Pow
/gps/ene/alpha -1
/gps/ene/min {edges[0]:.17e} MeV
/gps/ene/max {edges[-1]:.17e} MeV
/run/beamOn {events_per_chunk}
"""
    (directory / "calibration.chunk.mac").write_text(macro)
    (directory / "chunks").mkdir(exist_ok=True)
    _write_chunk_plan(directory, chunks, seed)
    config_path.write_text(json.dumps(config, indent=2) + "\n")


def _write_chunk_plan(directory, chunks, seed, entries=()):
    rng = np.random.default_rng(seed)
    previous = {(int(a), int(b)) for _, a, b in entries}
    seeds = set(previous)
    while len(seeds) < chunks:
        seeds.add(tuple(rng.integers(31, 1000000, size=2)))
    plan = "".join(f"{name} {a} {b}\n" for name, a, b in entries)
    plan += "".join(
        f"calibration {a:06d} {b:06d}\n" for a, b in sorted(seeds - previous)
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
            edges, RESPONSE_ENERGY_EDGES_MEV, rtol=1e-12, atol=0
        ):
            raise ValueError(
                "Compact phantom histograms must use the AtRIS response grid"
            )
        if len(fraction.member("fSumw2")) == 0:
            raise ValueError("Phantom histogram is missing per-bin squared sums")
        water_bin = (
            np.searchsorted(fraction.axes[1].edges(), WATER_DETECTOR_ID, side="right")
            - 1
        )
        counts = primary.values().astype(np.int64)
        totals = fraction.values()[:, water_bin]
        squares = fraction.variances()[:, water_bin]
        means = np.divide(totals, counts, out=np.zeros_like(totals), where=counts > 0)
        # Raw second-moment subtraction can round slightly below zero.
        deviations = np.maximum(0, squares - totals * means)
        detected = root["h2.detected"].values()[:, water_bin].astype(np.int64)
    return PhantomStatistics(counts, means, deviations, detected)


def read_phantom_events(path):
    """Read one native phantom chunk, or sum its older shower step records."""
    with uproot.open(path) as root:
        if "phantom_events" in root:
            arrays = root["phantom_events"].arrays(library="np")
            # Older compacted shower files contain water rows only; the native
            # mode names the scoring volume explicitly and can contain others.
            water = (
                arrays["detector_id"] == WATER_DETECTOR_ID
                if "detector_id" in arrays
                else slice(None)
            )
            return PhantomEvents(
                *(arrays[name][water] for name in PhantomEvents.__dataclass_fields__)
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
        water = steps["detector_id"] == WATER_DETECTOR_ID
        event_id = event_id[water]
        total = steps["energy_deposit_MeV"][water]
        nonionizing = steps["nonionizing_energy_deposit_MeV"][water]
        deposited += np.bincount(event_id, weights=total, minlength=event_count)
        ionizing += np.bincount(
            event_id, weights=total - nonionizing, minlength=event_count
        )
    if np.any(energy <= 0):
        raise ValueError(
            f"Missing primary energies in {path}; use phantom or shower output"
        )
    return PhantomEvents(energy, deposited, ionizing)


def compact_water_phantom_chunk(path):
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
            "calibration_compaction",
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


def read_water_phantom_events(run_directory):
    """Combine completed calibration chunks, keeping event IDs local to each.

    Read raw or compacted chunk ROOT files. Ordinary gathering deliberately
    omits the event records needed for event-by-event calibration.
    """
    directory = Path(run_directory)
    results = []
    for entry in read_chunk_plan(directory):
        name = chunk_name(entry)
        if (directory / "chunks" / (name + ".COMPLETE")).is_file():
            results.append(read_phantom_events(directory / "chunks" / (name + ".root")))
    if not results:
        raise ValueError("No completed calibration chunks")
    return PhantomEvents(
        *(
            np.concatenate([getattr(result, field) for result in results])
            for field in PhantomEvents.__dataclass_fields__
        )
    )
