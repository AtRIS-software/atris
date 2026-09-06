"""Plot particle-interface records written by AtRIS output mode 0."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .input_plotting import (
    log_norm,
    particle_symbol,
    positive_log_edges,
    read_layers,
    setup_shell_axis,
    shell_coordinates,
)
from .interface_output import read_interface_output


logger = logging.getLogger(__name__)


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
        invalid_count = np.count_nonzero(~valid_energy)
        logger.warning(
            "%s: ignoring %i non-positive or non-finite energy records",
            source_path.name,
            invalid_count,
        )
        records = records[valid_energy]
        kinetic_energy = kinetic_energy[valid_energy]
        source_energy = source_energy[valid_energy]
        if not records.size:
            raise ValueError(source_path.name + " contains no valid energy records")

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
    geometry_path = Path(simname + ".gdml")
    layers = read_layers(geometry_path)
    interface_ids, plot_positions, plot_edges = shell_coordinates(
        layers,
        location="outer",
    )
    interface_edges = np.concatenate(
        ([interface_ids[0] - 0.5], interface_ids + 0.5)
    )
    for mask, label in (
        (records["angle"] < 90, "Upward"),
        (records["angle"] >= 90, "Downward"),
    ):
        counts = [
            np.count_nonzero(mask & (interfaces == interface_id))
            for interface_id in interface_ids
        ]
        crossings_axis.step(plot_positions, counts, where="mid", label=label)
    setup_shell_axis(
        crossings_axis,
        plot_positions,
        axis_name="x",
    )
    crossings_axis.set_title("Crossings by distance from surface")
    crossings_axis.set_ylabel("Boundary crossings")
    crossings_axis.legend()

    kinetic_edges = positive_log_edges(kinetic_energy)
    interface_energy, _, _ = np.histogram2d(
        interfaces,
        kinetic_energy,
        bins=(interface_edges, kinetic_edges),
    )
    mesh = altitude_energy_axis.pcolormesh(
        plot_edges,
        kinetic_edges,
        interface_energy.T,
        cmap="Blues",
        norm=log_norm(interface_energy),
        shading="flat",
        rasterized=True,
    )
    setup_shell_axis(
        altitude_energy_axis,
        plot_positions,
        axis_name="x",
    )
    altitude_energy_axis.set_title("Kinetic energy by distance from surface")
    altitude_energy_axis.set_ylabel("Kinetic energy [MeV]")
    altitude_energy_axis.set_yscale("log")
    figure.colorbar(
        mesh,
        ax=altitude_energy_axis,
        orientation="horizontal",
        label="Boundary crossings",
    )

    source_edges = positive_log_edges(source_energy)
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
        norm=log_norm(energy_transfer),
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
