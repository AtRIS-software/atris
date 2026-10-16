"""Read and merge phantom sampling moments; reduce retained event records."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import uproot

from .chunks import chunk_name, read_chunk_plan
from .phantom_geometry import PHANTOM_DETECTOR_ID
from .phantom_table import ENERGY_EDGES_MEV, RESPONSE_ENERGY_BINS, ROOT_ENERGY_GRID_RTOL
from .root_records import iterate_ntuple


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
        if np.any(incident < ENERGY_EDGES_MEV[0]) or np.any(
            incident >= ENERGY_EDGES_MEV[-1]
        ):
            raise ValueError(
                "Phantom energies must lie inside the AtRIS response grid"
            )
        fraction = events.ionizing_energy_MeV / incident
        count = np.histogram(incident, ENERGY_EDGES_MEV)[0]
        total = np.histogram(incident, ENERGY_EDGES_MEV, weights=fraction)[0]
        mean = np.divide(
            total, count, out=np.zeros(RESPONSE_ENERGY_BINS), where=count > 0
        )
        bins = np.searchsorted(ENERGY_EDGES_MEV, incident, side="right") - 1
        deviations = np.bincount(
            bins, weights=(fraction - mean[bins]) ** 2, minlength=RESPONSE_ENERGY_BINS
        )
        detected = np.histogram(
            incident[events.ionizing_energy_MeV > threshold_MeV],
            ENERGY_EDGES_MEV,
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
        if edges.shape != ENERGY_EDGES_MEV.shape or not np.allclose(
            edges, ENERGY_EDGES_MEV, rtol=ROOT_ENERGY_GRID_RTOL, atol=0
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
