"""Prepare, refine, and inspect a PSF-defined spherical phantom."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import time

import numpy as np

from .chunks import chunk_name, read_chunk_plan
from .cli import HelpFormatter, add_version_argument, configure_logging
from .file_io import atomic_text_output
from .gdml import psf_to_gdml
from .particles import ion_pdg, particle_name, particle_source, pdg_code
from .phantom import DosePrecision, PHOTON_PDG, Phantom
from .phantom_geometry import (
    CM_PER_KM,
    DETECTOR_LAYER,
    PHANTOM_DETECTOR_ID,
    SOURCE_DISTANCE_RADII,
    TERMINATION_DETECTOR_IDS,
    TERMINATION_INNER_RADII,
    TERMINATION_OUTER_RADII,
    VACUUM_DENSITY_G_CM3,
    WORLD_MARGIN_RADII,
    sphere_psf,
)
from .phantom_statistics import PhantomStatistics, read_phantom_statistics
from .phantom_table import ENERGY_EDGES_MEV
from .psf import (
    DENSITY,
    DETECTOR_ID,
    FIRST_ELEMENT,
    INNER_RADIUS,
    OUTER_RADIUS,
    PRESSURE,
    PSF,
    STATE,
    write_psf,
)
from .root_records import read_ntuple


CHUNK_SEED_MIN = 31
CHUNK_SEED_MAX_EXCLUSIVE = 1_000_000
ENERGY_DECADES = int(round(np.log10(ENERGY_EDGES_MEV[-1] / ENERGY_EDGES_MEV[0])))
BINS_PER_DECADE = (len(ENERGY_EDGES_MEV) - 1) // ENERGY_DECADES
MAX_BATCH_EVENTS = 500_000_000
MAX_BATCH_GROWTH = 8
TARGET_BATCH_SECONDS = 600
COVERAGE_INTERVAL_BATCHES = 5
PROCESS_POLL_SECONDS = 1
CLOCK_GAP_SECONDS = 30
TERMINATION_GRACE_SECONDS = 10
BATCH_PURPOSES = {
    "initial coverage": "sample this species across the full energy range",
    "insufficient samples": "collect enough samples to estimate bin uncertainties",
    "unresolved uncertainty": "resolve unavailable bin uncertainties",
    "zero deposit": "investigate bins with no observed energy deposit",
    "timing pilot": "measure runtime for this species and energy range",
    "coverage": "revisit a less recently sampled energy range",
    "precision": "reduce uncertainty using the predicted gain per second",
    "batch count": "complete the requested batch count",
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildSettings:
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
        data = dict(data)
        target_names = [item.name for item in fields(DosePrecision)] + ["relative_tolerance"]
        precision = DosePrecision.from_dict({name: data.pop(name) for name in target_names if name in data})
        return cls(**data, precision=precision)

    def to_dict(self):
        data = asdict(self)
        data.update(data.pop("precision"))
        return data


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
    # Physical layers keep their materials; IDs 0/2 are vacuum stop shells.
    layers = np.concatenate((physical.layers.copy(), np.repeat(physical.layers[-1:], 2, axis=0)))
    layers[:-2, DETECTOR_ID] = -1
    layers[DETECTOR_LAYER, DETECTOR_ID] = PHANTOM_DETECTOR_ID
    layers[-2:, INNER_RADIUS] = np.array(TERMINATION_INNER_RADII) * radius_km
    layers[-2:, OUTER_RADIUS] = np.array(TERMINATION_OUTER_RADII) * radius_km
    layers[-2:, DETECTOR_ID] = TERMINATION_DETECTOR_IDS
    layers[-2:, DENSITY] = VACUUM_DENSITY_G_CM3
    layers[-2:, PRESSURE] = 0
    layers[-2:, STATE] = 0
    layers[-2:, FIRST_ELEMENT:] = 0
    layers[-2:, FIRST_ELEMENT] = 1
    geometry = PSF.from_layers(layers, physical.materials)
    write_psf(directory / "phantom.psf", geometry)
    psf_to_gdml(directory / "phantom.psf", directory / "phantom.gdml",
             world_margin_km=WORLD_MARGIN_RADII * radius_km)
    # The source range may cover only part of the shared response grid.
    np.savetxt(directory / "phantom.bins", ENERGY_EDGES_MEV)
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


def _save_json(path, value):
    with atomic_text_output(path) as output:
        output.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


@dataclass(frozen=True)
class Batch:
    """One sampling choice shared by schedule preview and batch execution."""

    pdg: int
    first_decade: int
    decades: int
    events: int
    reason: str
    forecast_seconds: float | None = None
    status: str = "planned"

    @property
    def species(self):
        return particle_name(self.pdg)

    @property
    def energy_range_MeV(self):
        start = BINS_PER_DECADE * self.first_decade
        return ENERGY_EDGES_MEV[[start, start + BINS_PER_DECADE * self.decades]]

    @classmethod
    def from_record(cls, record, *, status="planned"):
        return cls(record["pdg"], record["first_decade"], record["decades"],
                   record["events"], record["reason"], record.get("forecast_seconds"), status)

    def to_record(self):
        record = asdict(self)
        del record["status"]
        return record


@dataclass(init=False)
class PhantomBuilder:
    """A persistent phantom run, independent of a notebook session.

    A batch is one independently seeded native chunk. Completed inputs and
    outputs stay immutable; new adaptive batches live in new directories.
    """

    directory: Path
    settings: BuildSettings
    geometry: PSF

    def __str__(self):
        species = ", ".join(particle_name(code) for code in self.settings.pdg_codes)
        return "\n".join([
            f"Phantom sampling: {self.settings.stem}",
            f"Species: {species}",
            "Primaries per pilot: " + ", ".join(
                f"{particle_name(code)} {self._pilot_events(code):.3e}"
                for code in self.settings.pdg_codes),
            f"Production cut: {self.settings.production_cut_mm:g} mm",
            f"Relative dose tolerance: {self.settings.precision.relative_dose_tolerance:.1%}",
            f"Absolute dose tolerance: {self.settings.precision.absolute_dose_tolerance_Gy:.1e} Gy",
        ])

    def __init__(self, psf, pdg_codes, *, directory=".", name="phantom",
                pilot_events=1300, production_cut_mm=0.1, seed=314159,
                dose_rtol=0.05, dose_atol_Gy=1e-12,
                confidence_factor=1.96, physics_list="FTFP_BERT_HP", tracking_floor_eV=None):
        """Prepare sampling inputs from a PSF object or file and a species list.

        pilot_events is a common count or a mapping of species to counts.
        """
        directory = Path(directory).expanduser().resolve()
        geometry = sphere_psf(psf)
        if isinstance(psf, PSF):
            output = StringIO()
            psf.save(output)
            psf_bytes = output.getvalue().encode("utf-8")
        else:
            psf_bytes = Path(psf).expanduser().resolve().read_bytes()
        codes = list(dict.fromkeys(
            pdg_code(code) for code in pdg_codes
        ))
        if not codes or codes[0] != PHOTON_PDG:
            raise ValueError("Supply species with photon PDG 22 first for AtRIS export")
        for code in codes:
            particle_source(code)
        if not name or Path(name).name != name or name in (".", "..") or any(c.isspace() for c in name):
            raise ValueError("Name must be a single filename component without whitespace")
        if isinstance(pilot_events, dict):
            pilot_events = {str(pdg_code(code)): count for code, count in pilot_events.items()}
            if set(pilot_events) != {str(code) for code in codes}:
                raise ValueError("Pilot events must specify every configured species")
            counts = pilot_events.values()
        else:
            counts = [pilot_events]
        if any(not isinstance(count, int) or count < 1 for count in counts):
            raise ValueError("Pilot events must be positive integers")
        if not isinstance(seed, int) or seed < 0:
            raise ValueError("Seed must be a nonnegative integer")
        if not np.isfinite(production_cut_mm) or production_cut_mm <= 0:
            raise ValueError("Production cut must be finite and positive")
        if tracking_floor_eV is not None and (not np.isfinite(tracking_floor_eV) or tracking_floor_eV < 0):
            raise ValueError("tracking_floor_eV must be finite and nonnegative")
        settings = BuildSettings(stem=name, pdg_codes=codes,
                        pilot_events=pilot_events, production_cut_mm=production_cut_mm, seed=seed,
                        precision=DosePrecision(dose_rtol, dose_atol_Gy, confidence_factor),
                        physics_list=physics_list, psf_sha256=hashlib.sha256(psf_bytes).hexdigest(),
                        tracking_floor_eV=tracking_floor_eV)
        directory.mkdir(parents=True, exist_ok=True)
        config = directory / "phantom-build.json"
        if config.exists():
            build = type(self).open(directory)
            if build.settings != settings:
                raise FileExistsError("Different build settings require a new run directory")
            self.directory, self.settings = build.directory, build.settings
            self.geometry = build.geometry
            return
        if (directory / "batches.json").exists() or (directory / "batches").exists():
            raise FileExistsError("Existing batch records require their original build configuration")
        if (directory / "simulation.psf").exists() and (
            directory / "simulation.psf").read_bytes() != psf_bytes:
            raise FileExistsError("A different simulation.psf already exists")
        if not (directory / "simulation.psf").exists():
            (directory / "simulation.psf").write_bytes(psf_bytes)
        _save_json(config, settings.to_dict())
        _save_json(directory / "batches.json", [])
        self.directory, self.settings = directory, settings
        self.geometry = geometry

    @classmethod
    def open(cls, directory):
        """Open an existing build without preparing inputs or running transport."""
        directory = Path(directory).expanduser().resolve()
        settings = BuildSettings.from_dict(json.loads((directory / "phantom-build.json").read_text()))
        build = cls.__new__(cls)
        build.directory, build.settings = directory, settings
        build.geometry = build._read_geometry()
        return build

    def _read_geometry(self):
        contents = (self.directory / "simulation.psf").read_bytes()
        if hashlib.sha256(contents).hexdigest() != self.settings.psf_sha256:
            raise ValueError("The PSF changed after preparation; use a new run directory")
        return sphere_psf(PSF.read(StringIO(contents.decode("utf-8"))))

    def gather(self):
        """Return a Phantom from completed batches, without running or saving.

        Use this again after further sampling to refresh the result. The name,
        geometry and precision targets come from this build's settings.
        """
        geometry = self._read_geometry()
        settings = self.settings
        statistics = {code: PhantomStatistics.empty() for code in settings.pdg_codes}
        versions = set()
        for batch in self._batches():
            chunk = self._chunk(batch)
            if chunk.with_suffix(".COMPLETE").is_file():
                metadata = read_ntuple(chunk.with_suffix(".root"), "metadata",
                                       ("atris_version", "physics_list"))
                if set(metadata["physics_list"]) != {settings.physics_list}:
                    raise ValueError("Completed chunk physics list differs from the prepared build")
                versions.update(metadata["atris_version"])
                statistics[batch["pdg"]] += read_phantom_statistics(chunk.with_suffix(".root"))
        return Phantom.from_statistics(
            statistics, geometry=geometry,
            name=settings.stem,
            precision_settings=settings.precision,
            metadata=dict(physics_list=settings.physics_list,
                          production_cut_mm=settings.production_cut_mm,
                          atris_version=", ".join(sorted(versions)) or "not recorded",
                          generator="atris_tools.phantom_builder", psf_sha256=settings.psf_sha256,
                          sampling_settings=settings.to_dict()),
        )

    @contextmanager
    def _lock(self):
        with (self.directory / ".builder.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Another builder is using this run directory") from error
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _batches(self):
        return json.loads((self.directory / "batches.json").read_text())

    @property
    def radius_cm(self):
        return float(self.geometry.layers[DETECTOR_LAYER, OUTER_RADIUS] * CM_PER_KM)

    @property
    def density_g_cm3(self):
        return float(self.geometry.layers[DETECTOR_LAYER, DENSITY])

    def _chunk(self, batch):
        directory = self.directory / batch["directory"]
        return directory / "chunks" / chunk_name(read_chunk_plan(directory)[0])

    def precision(self, response=None):
        """Energy-only precision; empirical zeros remain unresolved, not complete."""
        response = self.gather() if response is None else response
        return response.precision(**asdict(self.settings.precision))

    def show_schedule(self, *, batches=1, adaptive=False, threads=1, time_limit_s=None):
        """Print a preview and return a tuple of Batch records, without running.

        The default count is one batch, as for run(). All selections use
        the current statistics, with previewed visits tracked only in memory.
        Actual adaptive choices are recalculated after each completed batch.
        Interrupted batches appear first.
        """
        if not isinstance(batches, int) or batches < 1 or not isinstance(threads, int) or threads < 1:
            raise ValueError("Batch and thread counts must be positive integers")
        if time_limit_s is not None and (not np.isfinite(time_limit_s) or time_limit_s <= 0):
            raise ValueError("time_limit_s must be a finite positive number of seconds")
        records = list(self._batches())
        pending = next((batch for batch in records
                        if not self._chunk(batch).with_suffix(".COMPLETE").exists()), None)
        response = self.gather()
        schedule = []
        rows = [("Batch", "Species", "K min (MeV)", "K max (MeV)", "Primaries", "Reason", "Status")]
        for _ in range(batches):
            if pending is not None:
                batch = Batch.from_record(pending, status="resume")
                pending = None
            else:
                batch = self._select(records, response, threads, adaptive, time_limit_s)
                if batch is None:
                    break
                records.append(batch.to_record())
            schedule.append(batch)
            lower, upper = batch.energy_range_MeV
            rows.append((
                str(len(schedule)), batch.species, f"{lower:.3e}", f"{upper:.3e}",
                f"{batch.events:.3e}", batch.reason, batch.status,
            ))
        widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
        print(f"Schedule preview: {len(schedule)} batches")
        for row in rows:
            print("  ".join(value.ljust(width) for value, width in zip(row, widths)))
        if adaptive:
            print("Preview uses current statistics; actual choices are recalculated after each batch.")
        return tuple(schedule)

    def _pilot_events(self, code):
        events = self.settings.pilot_events
        return events[str(code)] if isinstance(events, dict) else events

    def _select(self, batches, response, threads, adaptive, time_limit_s=None):
        codes = self.settings.pdg_codes
        for code in codes:
            if not any(batch["pdg"] == code for batch in batches):
                return Batch(code, 0, ENERGY_DECADES, self._pilot_events(code), "initial coverage")
        if not adaptive:
            code = codes[len(batches) % len(codes)]
            return Batch(code, 0, ENERGY_DECADES, self._pilot_events(code), "batch count")
        quality = self.precision(response)
        if quality["passed"].all():
            return None
        candidates = []
        for row, code in enumerate(codes):
            for decade in range(ENERGY_DECADES):
                group = slice(decade * BINS_PER_DECADE, (decade + 1) * BINS_PER_DECADE)
                if quality["passed"][row, group].all():
                    continue
                matching = [b for b in batches if b["pdg"] == code and b["first_decade"] == decade
                            and b["decades"] == 1 and b.get("threads") == threads
                            and b.get("fit_timing", False)
                            and b.get("completed_events", b["events"]) > 0
                            and np.isfinite(b.get("event_loop_seconds", b["wall_seconds"]))
                            and b.get("event_loop_seconds", b["wall_seconds"]) > 0]
                events = self._pilot_events(code)
                expected = None
                estimated_events = events
                if matching:
                    latest = matching[-1]
                    completed = latest.get("completed_events", latest["events"])
                    transport_seconds = latest.get("event_loop_seconds", latest["wall_seconds"])
                    rate = completed / transport_seconds
                    budget = TARGET_BATCH_SECONDS if time_limit_s is None else time_limit_s
                    events = max(events, min(MAX_BATCH_EVENTS, MAX_BATCH_GROWTH * completed,
                                 int(np.ceil(rate * budget))))
                    estimated_events = events if time_limit_s is None else min(events, rate * budget)
                    overhead = max(0, latest["wall_seconds"] - transport_seconds)
                    expected = estimated_events / rate + overhead
                unresolved = ~quality["resolved"][row, group]
                if unresolved.any() and not matching:
                    events = self._pilot_events(code)
                    estimated_events = events
                    expected = None
                n = response.sample_counts[row, group]
                q = quality["ratio"][row, group] ** 2
                gain = np.maximum(q - 1, 0) - np.maximum(q * n / (n + estimated_events / BINS_PER_DECADE) - 1, 0)
                score = float(np.nanmean(gain)) if np.isfinite(gain).any() else 0.0
                if expected is not None:
                    score /= expected
                last = max((i for i, b in enumerate(batches) if b["pdg"] == code
                            and b["first_decade"] <= decade < b["first_decade"] + b["decades"]), default=-1)
                candidates.append((code, decade, 1, events, score, last, unresolved.any(), expected))
        # Unmeasured ranges are explored before making runtime-based comparisons.
        exploratory = [c for c in candidates if c[6] or c[7] is None]
        coverage = len(batches) % COVERAGE_INTERVAL_BATCHES == COVERAGE_INTERVAL_BATCHES - 1
        selected = min(exploratory or candidates, key=lambda c: c[5]) if exploratory or coverage else max(candidates, key=lambda c: c[4])
        code, decade, width, events, _, _, unresolved, expected = selected
        if unresolved:
            row = codes.index(code)
            group = slice(decade * BINS_PER_DECADE, (decade + 1) * BINS_PER_DECADE)
            if (response.sample_counts[row, group] < 2).any():
                reason = "insufficient samples"
            elif not np.isfinite(quality["dose_error"][row, group]).all():
                reason = "unresolved uncertainty"
            else:
                reason = "zero deposit"
        elif expected is None:
            reason = "timing pilot"
        else:
            reason = "coverage" if coverage else "precision"
        return Batch(code, decade, width, events, reason, expected)

    def run(self, *, batches=1, adaptive=False, threads=1, time_limit_s=None):
        """Run a bounded number of batches, resuming a pending batch first."""
        if not isinstance(batches, int) or batches < 1 or not isinstance(threads, int) or threads < 1:
            raise ValueError("Batch and thread counts must be positive integers")
        if time_limit_s is not None and (not np.isfinite(time_limit_s) or time_limit_s <= 0):
            raise ValueError("time_limit_s must be a finite positive number of seconds")
        with self._lock():
            destination = "." if self.directory == Path.cwd() else str(self.directory)
            command = ["atris-build-phantom", destination, "--batches", str(batches),
                       "--threads", str(threads)]
            if adaptive:
                command.append("--adaptive")
            if time_limit_s is not None:
                command.extend(["--time-limit", str(time_limit_s)])
            logger.info("Running phantom sampling in folder %s", self.directory)
            logger.info("Batches: %d; transport threads per batch: %d", batches, threads)
            logger.info("Equivalent terminal command: %s", shlex.join(command))
            for _ in range(batches):
                records = self._batches()
                pending = next((b for b in records if not self._chunk(b).with_suffix(".COMPLETE").exists()), None)
                if pending is None:
                    selection = self._select(records, self.gather(), threads, adaptive, time_limit_s)
                    if selection is None:
                        break
                    relative = f"batches/batch-{len(records):06d}"
                    directory = self.directory / relative
                    directory.mkdir(parents=True, exist_ok=False)
                    prepare_phantom_batch(directory, selection.energy_range_MeV,
                        **particle_source(selection.pdg),
                        psf_path=self.directory / "simulation.psf",
                        events_per_chunk=selection.events, chunks=1, seed=self.settings.seed + len(records),
                        production_cut_mm=self.settings.production_cut_mm,
                        tracking_floor_eV=self.settings.tracking_floor_eV if self.settings.tracking_floor_eV is not None else 0)
                    pending = dict(directory=relative, **selection.to_record())
                    records.append(pending)
                pending["time_limit_seconds"] = time_limit_s
                _save_json(self.directory / "batches.json", records)
                self._execute(pending, threads)
                _save_json(self.directory / "batches.json", records)
            return self.gather()

    def _execute(self, batch, threads):
        if shutil.which("atris-run") is None or shutil.which("AtRIS") is None:
            raise RuntimeError("Both atris-run and the AtRIS executable must be on PATH")
        directory = self.directory / batch["directory"]
        chunk = self._chunk(batch)
        partial = [p for p in directory.joinpath("chunks").glob(chunk.name + "*") if p.suffix in (".root", ".log", ".FAILED")]
        if partial:
            archive = directory / ("interrupted-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
            archive.mkdir()
            for path in partial:
                shutil.move(str(path), archive / path.name)
        environment = os.environ.copy()
        environment["G4FORCENUMBEROFTHREADS"] = str(threads)
        environment.pop("ATRIS_TIME_LIMIT", None)
        if batch.get("time_limit_seconds") is not None:
            environment["ATRIS_TIME_LIMIT"] = str(batch["time_limit_seconds"])
        batch["threads"] = threads
        batch["started_utc"] = datetime.now(timezone.utc).isoformat()
        lower, upper = Batch.from_record(batch).energy_range_MeV
        purpose = BATCH_PURPOSES.get(batch["reason"], f"continue sampling ({batch['reason']})")
        logger.info(
            "Simulating up to %.3e primaries of %s (PDG %s) with kinetic energies "
            "from %.3e to %.3e MeV to %s.",
            batch["events"], particle_name(batch["pdg"]), batch["pdg"],
            lower, upper, purpose,
        )
        start = previous = time.time()
        interrupted_clock = False
        process = subprocess.Popen(["atris-run", str(directory), "--mode", "phantom",
                                    "--physics-list", self.settings.physics_list],
                                   env=environment, start_new_session=True)
        try:
            while process.poll() is None:
                time.sleep(PROCESS_POLL_SECONDS)
                now = time.time()
                interrupted_clock |= now - previous > CLOCK_GAP_SECONDS or now < previous
                previous = now
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, process.args)
        except BaseException:
            # Stop the launcher and its native child before releasing the run lock.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=TERMINATION_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        batch["finished_utc"] = datetime.now(timezone.utc).isoformat()
        batch["wall_seconds"] = time.time() - start
        if not chunk.with_suffix(".COMPLETE").exists():
            raise RuntimeError("Transport finished without a saved COMPLETE chunk")
        batch["completed_events"] = int(read_phantom_statistics(chunk.with_suffix(".root")).sample_counts.sum())
        log = chunk.with_suffix(".log")
        if log.exists():
            timing = re.search(r"event-loop wall time: (\S+) s", log.read_text())
            if timing:
                batch["event_loop_seconds"] = float(timing[1])
        duration = batch.get("event_loop_seconds", batch["wall_seconds"])
        batch["fit_timing"] = (not interrupted_clock and batch["completed_events"] > 0
                               and np.isfinite(duration) and duration > 0)


def main():
    parser = argparse.ArgumentParser(description="Run or inspect a prepared spherical phantom build.", formatter_class=HelpFormatter)
    add_version_argument(parser)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--batches", type=int, default=1, help="Maximum new/resumed batches to run (default: 1).")
    parser.add_argument("--adaptive", action="store_true", help="Refine energy uncertainty with exploration and coverage turns.")
    parser.add_argument("--threads", type=int, default=1, help="Geant4 transport threads (default: 1).")
    parser.add_argument("--time-limit", type=float, help="Event-loop time limit per batch in seconds (default: event-limited).")
    parser.add_argument("--postprocess-only", action="store_true", help="Read completed chunks and refresh exports/diagnostics without transport.")
    args = parser.parse_args()
    configure_logging(logging.INFO)
    build = PhantomBuilder.open(args.run_directory)
    if not args.postprocess_only:
        build.run(batches=args.batches, adaptive=args.adaptive, threads=args.threads, time_limit_s=args.time_limit)
    import matplotlib.pyplot as plt
    from .phantom_plotting import plot_creation_diagnostics, plot_sampling_precision

    with build._lock():
        phantom = build.gather()
        output = build.directory
        phantom.save(output)
        name = build.settings.stem
        for plot, filename in ((plot_creation_diagnostics, f"{name}_diagnostics.png"),
                               (plot_sampling_precision, f"{name}_sampling-precision.png")):
            axes = plot(phantom)
            figure = axes.flat[0].figure
            figure.savefig(output / filename)
            plt.close(figure)
    quality = build.precision(phantom)
    print(f"Resolved {quality['resolved'].sum()}/{phantom.sample_counts.size} bins; "
          f"passing {quality['passed'].sum()}; precision complete: {quality['passed'].all()}")
