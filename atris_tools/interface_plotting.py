"""Plot particle-interface records written by AtRIS output mode 0."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from .input_plotting import particle_symbol
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

    figure, axes = plt.subplots(ncols=2, nrows=2, figsize=(12, 10))
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
    axes[0, 0].barh(labels, counts)
    axes[0, 0].invert_yaxis()
    axes[0, 0].set_title("Particle species")
    axes[0, 0].set_xlabel("Boundary crossings")

    interfaces = records["interface"]
    interface_edges = np.arange(
        int(np.min(interfaces)) - 0.5,
        int(np.max(interfaces)) + 1.5,
    )
    for mask, label in (
        (records["angle"] < 90, "Angle < 90 degrees"),
        (records["angle"] >= 90, "Angle >= 90 degrees"),
    ):
        counts, _ = np.histogram(interfaces[mask], bins=interface_edges)
        axes[0, 1].stairs(counts, interface_edges, label=label)
    axes[0, 1].set_title("Crossings by interface")
    axes[0, 1].set_xlabel("Interface ID")
    axes[0, 1].set_ylabel("Boundary crossings")
    axes[0, 1].legend()

    kinetic_edges = _positive_log_edges(kinetic_energy)
    interface_energy, _, _ = np.histogram2d(
        interfaces,
        kinetic_energy,
        bins=(interface_edges, kinetic_edges),
    )
    mesh = axes[1, 0].pcolormesh(
        interface_edges,
        kinetic_edges,
        interface_energy.T,
        norm=_log_norm(interface_energy),
        shading="flat",
        rasterized=True,
    )
    axes[1, 0].set_title("Kinetic energy at each interface")
    axes[1, 0].set_xlabel("Interface ID")
    axes[1, 0].set_ylabel("Kinetic energy [MeV]")
    axes[1, 0].set_yscale("log")
    figure.colorbar(mesh, ax=axes[1, 0], label="Boundary crossings")

    source_edges = _positive_log_edges(source_energy)
    energy_transfer, _, _ = np.histogram2d(
        source_energy,
        kinetic_energy,
        bins=(source_edges, kinetic_edges),
    )
    mesh = axes[1, 1].pcolormesh(
        source_edges,
        kinetic_edges,
        energy_transfer.T,
        norm=_log_norm(energy_transfer),
        shading="flat",
        rasterized=True,
    )
    axes[1, 1].set_title("Primary and crossing energy")
    axes[1, 1].set_xlabel("Primary energy [MeV]")
    axes[1, 1].set_ylabel("Kinetic energy [MeV]")
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_yscale("log")
    figure.colorbar(mesh, ax=axes[1, 1], label="Boundary crossings")

    species = simname.capitalize()
    figure.suptitle(
        "%s mode-0 output: %i boundary crossings from %s"
        % (species, records.size, source_path.name)
    )
    figure.tight_layout()
    filename = simname + ".interfaces.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename
