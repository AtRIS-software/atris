"""Prepare, refine, and inspect a PSF-defined water-sphere calibration."""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import numpy as np

from .cli import HelpFormatter, add_version_argument
from .gather import atomic_text_output, chunk_name, read_chunk_plan
from .particles import particle_name, particle_source
from .root_output import read_ntuple
from .phantom_calibration import (
    PhantomResponse, PhantomStatistics, RESPONSE_ENERGY_EDGES_MEV,
    prepare_water_phantom, read_phantom_statistics,
)
from .psf import (
    PSF, INNER_RADIUS, OUTER_RADIUS, PHI_START, PHI_END, THETA_START, THETA_END,
    DENSITY, STATE, FIRST_ELEMENT, load_psf, read_psf_header,
)


def _save_json(path, value):
    with atomic_text_output(path) as output:
        output.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _water_sphere(path):
    """Read physical geometry from PSF; do not use atmospheric termination IDs."""
    psf = PSF(load_psf(path), " ".join(read_psf_header(path)))
    if len(psf.layers) != 1:
        raise ValueError("The water-sphere builder requires one unshielded PSF layer")
    layer = psf.layers[0]
    if not np.isfinite(layer).all() or layer[INNER_RADIUS] != 0 or layer[OUTER_RADIUS] <= 0:
        raise ValueError("The PSF must describe a finite sphere starting at radius zero")
    if not np.allclose(layer[[PHI_START, PHI_END, THETA_START, THETA_END]],
                       [0, 2 * np.pi, 0, np.pi], rtol=0, atol=1e-10):
        raise ValueError("The PSF must cover a complete sphere")
    elements = read_psf_header(path)[1:]
    fractions = dict(zip(elements, layer[FIRST_ELEMENT:]))
    water = {"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528}
    if layer[STATE] != 2 or set(fractions) != set(water) or any(
        not np.isclose(fractions[key], water[key], rtol=0, atol=1e-6) for key in water
    ):
        raise ValueError("This builder supports liquid H2O only, with explicit H/O mass fractions")
    if layer[DENSITY] <= 0:
        raise ValueError("Water density must be positive")
    return float(layer[OUTER_RADIUS] * 1e5), float(layer[DENSITY])


@dataclass
class PhantomBuild:
    """A persistent calibration run, independent of a notebook session.

    A batch is one independently seeded native chunk. Completed inputs and
    outputs stay immutable; new adaptive batches live in new directories.
    """

    directory: Path
    settings: dict

    @classmethod
    def prepare(cls, directory, psf_path, pdg_codes, *, stem="water-sphere",
                pilot_events=1300, production_cut_mm=0.1, seed=314159,
                relative_tolerance=0.05, absolute_dose_tolerance_Gy=1e-12,
                confidence_factor=1.96, physics_list="FTFP_BERT_HP"):
        """Configure a run without launching transport. Repeating it is a no-op."""
        directory = Path(directory).expanduser().resolve()
        psf_path = Path(psf_path).expanduser().resolve()
        radius, density = _water_sphere(psf_path)
        codes = list(dict.fromkeys(int(code) for code in pdg_codes))
        if not codes or codes[0] != 22:
            raise ValueError("Supply species with photon PDG 22 first for AtRIS export")
        for code in codes:
            particle_source(code)
        if not stem or Path(stem).name != stem or stem in (".", ".."):
            raise ValueError("Stem must be a single filename component")
        if not isinstance(pilot_events, int) or pilot_events < 1:
            raise ValueError("Pilot events must be a positive integer")
        if not isinstance(seed, int) or seed < 0:
            raise ValueError("Seed must be a nonnegative integer")
        if not all(np.isfinite(x) and x > 0 for x in (
            production_cut_mm, relative_tolerance, absolute_dose_tolerance_Gy, confidence_factor
        )):
            raise ValueError("Cuts and precision settings must be finite and positive")
        settings = dict(stem=stem, pdg_codes=codes, radius_cm=radius, density_g_cm3=density,
                        pilot_events=pilot_events, production_cut_mm=production_cut_mm, seed=seed,
                        relative_tolerance=relative_tolerance,
                        absolute_dose_tolerance_Gy=absolute_dose_tolerance_Gy,
                        confidence_factor=confidence_factor, physics_list=physics_list,
                        psf_sha256=hashlib.sha256(psf_path.read_bytes()).hexdigest())
        directory.mkdir(parents=True, exist_ok=True)
        config = directory / "phantom-build.json"
        if config.exists():
            build = cls.open(directory)
            if build.settings != settings:
                raise FileExistsError("Different build settings require a new run directory")
            return build
        if (directory / "batches.json").exists() or (directory / "batches").exists():
            raise FileExistsError("Existing batch records require their original build configuration")
        if (directory / "simulation.psf").exists() and (
            directory / "simulation.psf").read_bytes() != psf_path.read_bytes():
            raise FileExistsError("A different simulation.psf already exists")
        if psf_path != directory / "simulation.psf":
            shutil.copyfile(psf_path, directory / "simulation.psf")
        _save_json(config, settings)
        _save_json(directory / "batches.json", [])
        return cls(directory, settings)

    @classmethod
    def open(cls, directory):
        directory = Path(directory).expanduser().resolve()
        settings = json.loads((directory / "phantom-build.json").read_text())
        actual = hashlib.sha256((directory / "simulation.psf").read_bytes()).hexdigest()
        if actual != settings["psf_sha256"]:
            raise ValueError("The PSF changed after preparation; use a new run directory")
        return cls(directory, settings)

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

    def _chunk(self, batch):
        directory = self.directory / batch["directory"]
        return directory / "chunks" / chunk_name(read_chunk_plan(directory)[0])

    def response(self):
        """Aggregate only saved COMPLETE chunks; retain NaN for missing estimates."""
        statistics = {code: PhantomStatistics.empty() for code in self.settings["pdg_codes"]}
        versions = set()
        for batch in self._batches():
            chunk = self._chunk(batch)
            if chunk.with_suffix(".COMPLETE").is_file():
                metadata = read_ntuple(chunk.with_suffix(".root"), "metadata",
                                       ("atris_version", "physics_list"))
                if set(metadata["physics_list"]) != {self.settings["physics_list"]}:
                    raise ValueError("Completed chunk physics list differs from the prepared build")
                versions.update(metadata["atris_version"])
                statistics[batch["pdg"]] += read_phantom_statistics(chunk.with_suffix(".root"))
        return PhantomResponse.from_statistics(
            statistics, radius_cm=self.settings["radius_cm"],
            density_g_cm3=self.settings["density_g_cm3"],
            metadata=dict(physics_list=self.settings["physics_list"],
                          production_cut_mm=self.settings["production_cut_mm"],
                          atris_version=", ".join(sorted(versions)) or "not recorded",
                          generator="atris_tools.phantom_builder", psf_sha256=self.settings["psf_sha256"]),
        )

    def precision(self, response=None):
        """Energy-only precision; empirical zeros remain unresolved, not complete."""
        response = self.response() if response is None else response
        centres = (RESPONSE_ENERGY_EDGES_MEV[:-1] + RESPONSE_ENERGY_EDGES_MEV[1:]) / 2
        factor = centres * 1.602176634e-13 / (response.mass_g * 1e-3)
        dose = response.energy_fraction * factor
        error = response.fraction_standard_error * factor
        resolved = (response.sample_counts > 1) & np.isfinite(error) & (dose > 0)
        target = np.maximum(self.settings["absolute_dose_tolerance_Gy"],
                            self.settings["relative_tolerance"] * np.abs(dose))
        ratio = self.settings["confidence_factor"] * error / target
        passed = resolved & (ratio <= 1)
        return dict(dose=dose, dose_error=error, ratio=ratio, resolved=resolved, passed=passed)

    def _select(self, batches, response, threads, adaptive):
        codes = self.settings["pdg_codes"]
        for code in codes:
            if not any(batch["pdg"] == code for batch in batches):
                return code, 0, 13, self.settings["pilot_events"], "initial coverage", None
        if not adaptive:
            code = codes[len(batches) % len(codes)]
            return code, 0, 13, self.settings["pilot_events"], "uniform batch", None
        quality = self.precision(response)
        if quality["passed"].all():
            return None
        candidates = []
        for row, code in enumerate(codes):
            for decade in range(13):
                group = slice(decade * 50, (decade + 1) * 50)
                if quality["passed"][row, group].all():
                    continue
                matching = [b for b in batches if b["pdg"] == code and b["first_decade"] == decade
                            and b["decades"] == 1 and b.get("threads") == threads
                            and b.get("fit_timing", False)]
                events = self.settings["pilot_events"]
                expected = None
                if matching:
                    latest = matching[-1]
                    events = max(events, min(500_000_000, 8 * latest["events"],
                                 int(latest["events"] * 600 / latest["wall_seconds"])))
                    expected = latest["wall_seconds"] * events / latest["events"]
                unresolved = ~quality["resolved"][row, group]
                if unresolved.any():
                    events = self.settings["pilot_events"]
                    expected = None
                n = response.sample_counts[row, group]
                q = quality["ratio"][row, group] ** 2
                gain = np.maximum(q - 1, 0) - np.maximum(q * n / (n + events / 50) - 1, 0)
                score = float(np.nanmean(gain)) if np.isfinite(gain).any() else 0.0
                if expected is not None:
                    score /= expected
                last = max((i for i, b in enumerate(batches) if b["pdg"] == code
                            and b["first_decade"] <= decade < b["first_decade"] + b["decades"]), default=-1)
                candidates.append((code, decade, 1, events, score, last, unresolved.any(), expected))
        # Unmeasured ranges are explored before making runtime-based comparisons.
        exploratory = [c for c in candidates if c[6] or c[7] is None]
        coverage = len(batches) % 5 == 4
        selected = min(exploratory or candidates, key=lambda c: c[5]) if exploratory or coverage else max(candidates, key=lambda c: c[4])
        code, decade, width, events, _, _, unresolved, expected = selected
        reason = "exploration" if exploratory else "coverage" if coverage else "predicted precision gain per second"
        return code, decade, width, events, reason, expected

    def run(self, *, batches=1, adaptive=False, threads=1):
        """Run a bounded number of batches, resuming a pending batch first."""
        if not isinstance(batches, int) or batches < 1 or not isinstance(threads, int) or threads < 1:
            raise ValueError("Batch and thread counts must be positive integers")
        with self._lock():
            for _ in range(batches):
                records = self._batches()
                pending = next((b for b in records if not self._chunk(b).with_suffix(".COMPLETE").exists()), None)
                if pending is None:
                    selection = self._select(records, self.response(), threads, adaptive)
                    if selection is None:
                        break
                    code, decade, width, events, reason, forecast = selection
                    relative = f"batches/batch-{len(records):06d}"
                    directory = self.directory / relative
                    directory.mkdir(parents=True, exist_ok=False)
                    edges = RESPONSE_ENERGY_EDGES_MEV[[50 * decade, 50 * (decade + width)]]
                    prepare_water_phantom(directory, edges, **particle_source(code),
                        radius_cm=self.settings["radius_cm"], density_g_cm3=self.settings["density_g_cm3"],
                        events_per_chunk=events, chunks=1, seed=self.settings["seed"] + len(records),
                        production_cut_mm=self.settings["production_cut_mm"], tracking_floor_eV=0)
                    pending = dict(directory=relative, pdg=code, first_decade=decade, decades=width,
                                   events=events, reason=reason, forecast_seconds=forecast)
                    records.append(pending)
                    _save_json(self.directory / "batches.json", records)
                self._execute(pending, threads)
                _save_json(self.directory / "batches.json", records)
            return self.response()

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
        batch["threads"] = threads
        batch["started_utc"] = datetime.now(timezone.utc).isoformat()
        print(f"{particle_name(batch['pdg'])} (PDG {batch['pdg']}): {batch['events']} primaries, {batch['reason']}", flush=True)
        start = previous = time.time()
        interrupted_clock = False
        process = subprocess.Popen(["atris-run", str(directory), "--mode", "phantom",
                                    "--physics-list", self.settings["physics_list"]],
                                   env=environment, start_new_session=True)
        try:
            while process.poll() is None:
                time.sleep(1)
                now = time.time()
                interrupted_clock |= now - previous > 30 or now < previous
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
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        batch["finished_utc"] = datetime.now(timezone.utc).isoformat()
        batch["wall_seconds"] = time.time() - start
        batch["fit_timing"] = not interrupted_clock
        if not chunk.with_suffix(".COMPLETE").exists():
            raise RuntimeError("Transport finished without a saved COMPLETE chunk")

    def postprocess(self):
        """Write partial response exports and creation diagnostics without transport."""
        from .phantom_diagnostics import plot_creation_diagnostics
        with self._lock():
            response = self.response()
            output = self.directory / "export"
            response.write(output, stem=self.settings["stem"], allow_partial=True)
            quality = self.precision(response)
            _save_json(output / "sampling-state.json", dict(
                total_bins=int(response.sample_counts.size),
                sampled_bins=int(np.count_nonzero(response.sample_counts)),
                resolved_bins=int(quality["resolved"].sum()), passing_bins=int(quality["passed"].sum()),
                precision_complete=bool(quality["passed"].all()),
                relative_tolerance=self.settings["relative_tolerance"],
                absolute_dose_tolerance_Gy=self.settings["absolute_dose_tolerance_Gy"],
                confidence_factor=self.settings["confidence_factor"], counting_drives_sampling=False))
            plot_creation_diagnostics(response, output / "diagnostics.png")
            return response


def main():
    parser = argparse.ArgumentParser(description="Run or inspect a prepared water-sphere phantom build.", formatter_class=HelpFormatter)
    add_version_argument(parser)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--batches", type=int, default=1, help="Maximum new/resumed batches to run (default: 1).")
    parser.add_argument("--adaptive", action="store_true", help="Refine energy uncertainty with exploration and coverage turns.")
    parser.add_argument("--threads", type=int, default=1, help="Geant4 transport threads (default: 1).")
    parser.add_argument("--postprocess-only", action="store_true", help="Read completed chunks and refresh exports/diagnostics without transport.")
    args = parser.parse_args()
    build = PhantomBuild.open(args.run_directory)
    if not args.postprocess_only:
        build.run(batches=args.batches, adaptive=args.adaptive, threads=args.threads)
    response = build.postprocess()
    quality = build.precision(response)
    print(f"Resolved {quality['resolved'].sum()}/{response.sample_counts.size} bins; "
          f"passing {quality['passed'].sum()}; precision complete: {quality['passed'].all()}")
