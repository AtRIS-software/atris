"""Prepare, refine, and inspect a PSF-defined water-sphere calibration."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
from io import StringIO
import json
import logging
import os
import re
from pathlib import Path
import shutil
import shlex
import signal
import subprocess
import time

import numpy as np

from .cli import HelpFormatter, add_version_argument, configure_logging
from .gather import atomic_text_output, chunk_name, read_chunk_plan
from .particles import particle_source, particle_name, pdg_code
from .phantom_calibration import (
    Phantom, RESPONSE_ENERGY_EDGES_MEV,
    prepare_water_phantom, water_sphere_psf, read_phantom_statistics,
    CM_PER_KM, PHOTON_PDG, _read_dose_settings,
)
from .psf import PSF, OUTER_RADIUS, DENSITY

# Whole decades are the adaptive scheduling units on the fixed response grid.
ENERGY_DECADES = int(round(np.log10(RESPONSE_ENERGY_EDGES_MEV[-1] / RESPONSE_ENERGY_EDGES_MEV[0])))
BINS_PER_DECADE = (len(RESPONSE_ENERGY_EDGES_MEV) - 1) // ENERGY_DECADES
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

def _save_json(path, value):
    with atomic_text_output(path) as output:
        output.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


@dataclass(init=False)
class PhantomBuilder:
    """A persistent calibration run, independent of a notebook session.

    A batch is one independently seeded native chunk. Completed inputs and
    outputs stay immutable; new adaptive batches live in new directories.
    """

    directory: Path
    settings: dict

    def __str__(self):
        species = ", ".join(particle_name(code) for code in self.settings["pdg_codes"])
        return "\n".join([
            f"Phantom sampling: {self.settings['stem']}",
            f"Species: {species}",
            "Primaries per pilot: " + ", ".join(
                f"{particle_name(code)} {self._pilot_events(code):.3e}"
                for code in self.settings["pdg_codes"]),
            f"Production cut: {self.settings['production_cut_mm']:g} mm",
            f"Relative dose tolerance: {self.settings['relative_dose_tolerance']:.1%}",
            f"Absolute dose tolerance: {self.settings['absolute_dose_tolerance_Gy']:.1e} Gy",
        ])

    def __init__(self, psf, pdg_codes, *, directory=".", name="water-sphere",
                pilot_events=1300, production_cut_mm=0.1, seed=314159,
                dose_rtol=0.05, dose_atol_Gy=1e-12,
                confidence_factor=1.96, physics_list="FTFP_BERT_HP", tracking_floor_eV=None):
        """Prepare sampling inputs from a PSF object or file and a species list.

        pilot_events is a common count or a mapping of species to counts.
        """
        directory = Path(directory).expanduser().resolve()
        water_sphere_psf(psf)
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
        if not all(np.isfinite(x) and x > 0 for x in (
            production_cut_mm, dose_rtol, dose_atol_Gy, confidence_factor
        )):
            raise ValueError("Cuts and precision settings must be finite and positive")
        settings = dict(stem=name, pdg_codes=codes,
                        pilot_events=pilot_events, production_cut_mm=production_cut_mm, seed=seed,
                        relative_dose_tolerance=dose_rtol,
                        absolute_dose_tolerance_Gy=dose_atol_Gy,
                        confidence_factor=confidence_factor, physics_list=physics_list,
                        psf_sha256=hashlib.sha256(psf_bytes).hexdigest())
        if tracking_floor_eV is not None:
            if not np.isfinite(tracking_floor_eV) or tracking_floor_eV < 0:
                raise ValueError("tracking_floor_eV must be finite and nonnegative")
            settings["tracking_floor_eV"] = tracking_floor_eV
        directory.mkdir(parents=True, exist_ok=True)
        config = directory / "phantom-build.json"
        if config.exists():
            build = type(self).open(directory)
            if build.settings != settings:
                raise FileExistsError("Different build settings require a new run directory")
            self.directory, self.settings = build.directory, build.settings
            return
        if (directory / "batches.json").exists() or (directory / "batches").exists():
            raise FileExistsError("Existing batch records require their original build configuration")
        if (directory / "simulation.psf").exists() and (
            directory / "simulation.psf").read_bytes() != psf_bytes:
            raise FileExistsError("A different simulation.psf already exists")
        if not (directory / "simulation.psf").exists():
            (directory / "simulation.psf").write_bytes(psf_bytes)
        _save_json(config, settings)
        _save_json(directory / "batches.json", [])
        self.directory, self.settings = directory, settings

    @classmethod
    def open(cls, directory):
        directory = Path(directory).expanduser().resolve()
        settings = _read_dose_settings(json.loads((directory / "phantom-build.json").read_text()))
        build = cls.__new__(cls)
        build.directory, build.settings = directory, settings
        build._geometry()
        return build

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
        return self._geometry()[0]

    @property
    def density_g_cm3(self):
        return self._geometry()[1]

    def _geometry(self):
        path = self.directory / "simulation.psf"
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.settings["psf_sha256"]:
            raise ValueError("The PSF changed after preparation; use a new run directory")
        layer = water_sphere_psf(path).layers[0]
        return float(layer[OUTER_RADIUS] * CM_PER_KM), float(layer[DENSITY])

    def _chunk(self, batch):
        directory = self.directory / batch["directory"]
        return directory / "chunks" / chunk_name(read_chunk_plan(directory)[0])

    def precision(self, response=None):
        """Energy-only precision; empirical zeros remain unresolved, not complete."""
        response = Phantom.gather(directory=self.directory) if response is None else response
        return response.precision(**{key: self.settings[key] for key in (
            "relative_dose_tolerance", "absolute_dose_tolerance_Gy", "confidence_factor")})

    def show_schedule(self, *, batches=None, adaptive=False, threads=1, time_limit_s=None):
        """Preview batches without writing inputs or running transport.

        The default count covers the configured species once. All selections use
        the current statistics, with previewed visits tracked only in memory.
        Actual adaptive choices are recalculated after each completed batch.
        Interrupted batches appear first.
        """
        batches = len(self.settings["pdg_codes"]) if batches is None else batches
        if not isinstance(batches, int) or batches < 1 or not isinstance(threads, int) or threads < 1:
            raise ValueError("Batch and thread counts must be positive integers")
        if time_limit_s is not None and (not np.isfinite(time_limit_s) or time_limit_s <= 0):
            raise ValueError("time_limit_s must be a finite positive number of seconds")
        records = list(self._batches())
        pending = next((batch for batch in records
                        if not self._chunk(batch).with_suffix(".COMPLETE").exists()), None)
        response = Phantom.gather(directory=self.directory)
        entries = []
        for _ in range(batches):
            if pending is not None:
                batch = pending
                pending = None
                status = "resume"
            else:
                selection = self._select(records, response, threads, adaptive, time_limit_s)
                if selection is None:
                    break
                code, decade, width, events, reason, forecast = selection
                batch = dict(pdg=code, first_decade=decade, decades=width,
                             events=events, reason=reason, forecast_seconds=forecast)
                records.append(batch)
                status = "planned"
            start = BINS_PER_DECADE * batch["first_decade"]
            stop = start + BINS_PER_DECADE * batch["decades"]
            entries.append((
                str(len(entries) + 1), particle_name(batch["pdg"]),
                f"{RESPONSE_ENERGY_EDGES_MEV[start]:.3e}",
                f"{RESPONSE_ENERGY_EDGES_MEV[stop]:.3e}",
                f"{batch['events']:.3e}", batch["reason"], status,
            ))
        rows = [("Batch", "Species", "K min (MeV)", "K max (MeV)", "Primaries", "Reason", "Status"),
                *entries]
        widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
        print(f"Schedule preview: {len(entries)} batches")
        for row in rows:
            print("  ".join(value.ljust(width) for value, width in zip(row, widths)))
        if adaptive:
            print("Preview uses current statistics; actual choices are recalculated after each batch.")

    def _pilot_events(self, code):
        events = self.settings["pilot_events"]
        return events[str(code)] if isinstance(events, dict) else events

    def _select(self, batches, response, threads, adaptive, time_limit_s=None):
        codes = self.settings["pdg_codes"]
        for code in codes:
            if not any(batch["pdg"] == code for batch in batches):
                return code, 0, ENERGY_DECADES, self._pilot_events(code), "initial coverage", None
        if not adaptive:
            code = codes[len(batches) % len(codes)]
            return code, 0, ENERGY_DECADES, self._pilot_events(code), "batch count", None
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
        return code, decade, width, events, reason, expected

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
                    selection = self._select(records, Phantom.gather(directory=self.directory), threads, adaptive, time_limit_s)
                    if selection is None:
                        break
                    code, decade, width, events, reason, forecast = selection
                    relative = f"batches/batch-{len(records):06d}"
                    directory = self.directory / relative
                    directory.mkdir(parents=True, exist_ok=False)
                    edges = RESPONSE_ENERGY_EDGES_MEV[[BINS_PER_DECADE * decade, BINS_PER_DECADE * (decade + width)]]
                    prepare_water_phantom(directory, edges, **particle_source(code),
                        psf_path=self.directory / "simulation.psf",
                        events_per_chunk=events, chunks=1, seed=self.settings["seed"] + len(records),
                        production_cut_mm=self.settings["production_cut_mm"],
                        tracking_floor_eV=self.settings.get("tracking_floor_eV", 0))
                    pending = dict(directory=relative, pdg=code, first_decade=decade, decades=width,
                                   events=events, reason=reason, forecast_seconds=forecast)
                    records.append(pending)
                    _save_json(self.directory / "batches.json", records)
                pending["time_limit_seconds"] = time_limit_s
                _save_json(self.directory / "batches.json", records)
                self._execute(pending, threads)
                _save_json(self.directory / "batches.json", records)
            return Phantom.gather(directory=self.directory)

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
        start_bin = BINS_PER_DECADE * batch["first_decade"]
        stop_bin = start_bin + BINS_PER_DECADE * batch["decades"]
        purpose = BATCH_PURPOSES.get(batch["reason"], f"continue sampling ({batch['reason']})")
        logger.info(
            "Simulating up to %.3e primaries of %s (PDG %s) with kinetic energies "
            "from %.3e to %.3e MeV to %s.",
            batch["events"], particle_name(batch["pdg"]), batch["pdg"],
            RESPONSE_ENERGY_EDGES_MEV[start_bin], RESPONSE_ENERGY_EDGES_MEV[stop_bin], purpose,
        )
        start = previous = time.time()
        interrupted_clock = False
        process = subprocess.Popen(["atris-run", str(directory), "--mode", "phantom",
                                    "--physics-list", self.settings["physics_list"]],
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
    parser = argparse.ArgumentParser(description="Run or inspect a prepared water-sphere phantom build.", formatter_class=HelpFormatter)
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
    from .phantom_diagnostics import plot_creation_diagnostics, plot_sampling_precision

    with build._lock():
        phantom = Phantom.gather(directory=build.directory)
        output = build.directory
        phantom.save(output)
        name = build.settings["stem"]
        for plot, filename in ((plot_creation_diagnostics, f"{name}_diagnostics.png"),
                               (plot_sampling_precision, f"{name}_sampling-precision.png")):
            axes = plot(phantom)
            figure = axes.flat[0].figure
            figure.savefig(output / filename)
            plt.close(figure)
    quality = build.precision(phantom)
    print(f"Resolved {quality['resolved'].sum()}/{phantom.sample_counts.size} bins; "
          f"passing {quality['passed'].sum()}; precision complete: {quality['passed'].all()}")
