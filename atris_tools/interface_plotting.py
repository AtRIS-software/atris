"""Plot particle-interface records written by AtRIS output mode 0."""

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from .input_plotting import particle_symbol, read_interface_altitudes
from .interface_output import read_interface_output


def _log_norm(data):
    positive = data[np.isfinite(data) & (data > 0)]
    if not positive.size:
        return None
    return LogNorm(vmin=np.min(positive), vmax=np.max(positive))


def _positive_log_edges(values, bins=80):
    positive = values[np.isfinite(values) & (values > 0)]
    if not positive.size:
        raise ValueError("No positive finite energy values are available")
    lower = np.min(positive)
    upper = np.max(positive)
    if lower == upper:
        factor = np.sqrt(10.0)
        lower /= factor
        upper *= factor
    return np.geomspace(lower, upper, bins + 1)


def _centers_to_edges(centers):
    if centers.size == 1:
        width = max(abs(centers[0]) * 0.05, 1.0)
        return np.array([max(0.0, centers[0] - width), centers[0] + width])
    midpoints = (centers[:-1] + centers[1:]) / 2.0
    return np.concatenate(
        (
            [max(0.0, centers[0] - (midpoints[0] - centers[0]))],
            midpoints,
            [centers[-1] + (centers[-1] - midpoints[-1])],
        )
    )


def plot_interface_output(simname):
    """Plot particle boundary crossings recorded by AtRIS output mode 0."""
    records, source_path = read_interface_output(simname)
    if not records.size:
        raise ValueError(source_path.name + " contains no records")
    if np.any(records["angle"] > 180):
        raise ValueError(source_path.name + " contains angles above 180 degrees")

    kinetic_energy = records["kinetic_energy"].astype(float)
    source_energy = records["source_energy"].astype(float)
    valid_energy = (
        np.isfinite(kinetic_energy)
        & np.isfinite(source_energy)
        & (kinetic_energy > 0)
        & (source_energy > 0)
    )
    if not np.all(valid_energy):
        raise ValueError(
            "%s contains %i non-positive or non-finite energy records"
            % (source_path.name, np.count_nonzero(~valid_energy))
        )

    figure, axes = plt.subplots(
        ncols=2, nrows=2, figsize=(12, 11), layout="constrained"
    )
    species_axis = axes[0, 0]
    crossings_axis = axes[0, 1]
    energy_transfer_axis = axes[1, 0]
    altitude_energy_axis = axes[1, 1]
    particle_codes, particle_counts = np.unique(
        records["pdg"], return_counts=True
    )
    order = np.argsort(particle_counts)[::-1]
    particle_codes = particle_codes[order]
    particle_counts = particle_counts[order]
    display_limit = 12
    labels = [
        particle_symbol(int(code)) for code in particle_codes[:display_limit]
    ]
    counts = particle_counts[:display_limit]
    if particle_codes.size > display_limit:
        labels.append("other")
        counts = np.append(counts, np.sum(particle_counts[display_limit:]))
    species_axis.barh(labels, counts)
    species_axis.invert_yaxis()
    species_axis.set_title("Particle species")
    species_axis.set_xlabel("Boundary crossings")
    species_axis.set_xscale("log")

    interfaces = records["interface"]
    interface_ids = np.arange(
        int(np.min(interfaces)), int(np.max(interfaces)) + 1
    )
    interface_edges = np.concatenate(
        ([interface_ids[0] - 0.5], interface_ids + 0.5)
    )
    interface_positions = interface_ids.astype(float)
    display_edges = interface_edges
    interface_label = "Interface ID"
    geometry_path = Path(simname + ".gdml")
    if geometry_path.is_file():
        altitude_by_id = read_interface_altitudes(geometry_path)
        interface_positions = np.asarray(
            [altitude_by_id[int(interface_id)] for interface_id in interface_ids]
        )
        display_edges = _centers_to_edges(interface_positions)
        interface_label = "Altitude [km]"
    for mask, label in (
        (records["angle"] < 90, "Upward"),
        (records["angle"] >= 90, "Downward"),
    ):
        counts = [
            np.count_nonzero(mask & (interfaces == interface_id))
            for interface_id in interface_ids
        ]
        crossings_axis.step(
            interface_positions, counts, where="mid", label=label
        )
    crossings_axis.set_title("Crossings by altitude")
    crossings_axis.set_xlabel(interface_label)
    crossings_axis.set_ylabel("Boundary crossings")
    crossings_axis.legend()

    kinetic_edges = _positive_log_edges(kinetic_energy)
    interface_energy, _, _ = np.histogram2d(
        interfaces,
        kinetic_energy,
        bins=(interface_edges, kinetic_edges),
    )
    mesh = altitude_energy_axis.pcolormesh(
        display_edges,
        kinetic_edges,
        interface_energy.T,
        cmap="Blues",
        norm=_log_norm(interface_energy),
        shading="flat",
        rasterized=True,
    )
    altitude_energy_axis.set_title("Kinetic energy by altitude")
    altitude_energy_axis.set_xlabel(interface_label)
    altitude_energy_axis.set_ylabel("Kinetic energy [MeV]")
    altitude_energy_axis.set_yscale("log")
    figure.colorbar(
        mesh,
        ax=altitude_energy_axis,
        orientation="horizontal",
        label="Boundary crossings",
    )

    source_edges = _positive_log_edges(source_energy)
    energy_transfer, _, _ = np.histogram2d(
        source_energy,
        kinetic_energy,
        bins=(source_edges, kinetic_edges),
    )
    mesh = energy_transfer_axis.pcolormesh(
        source_edges,
        kinetic_edges,
        energy_transfer.T,
        cmap="Oranges",
        norm=_log_norm(energy_transfer),
        shading="flat",
        rasterized=True,
    )
    energy_transfer_axis.set_title("Primary and crossing energy")
    energy_transfer_axis.set_xlabel("Primary energy [MeV]")
    energy_transfer_axis.set_ylabel("Kinetic energy [MeV]")
    energy_transfer_axis.set_xscale("log")
    energy_transfer_axis.set_yscale("log")
    figure.colorbar(
        mesh,
        ax=energy_transfer_axis,
        orientation="horizontal",
        label="Boundary crossings",
    )

    species = simname.capitalize()
    figure.suptitle(
        "%s mode-0 output: %i boundary crossings from %s"
        % (species, records.size, source_path.name)
    )
    filename = simname + ".interfaces.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename
