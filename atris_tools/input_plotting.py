"""Create quick-look plots of the files supplied to AtRIS."""

import os
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np

from .phantoms import read_phantoms


PHANTOM_ENERGY_EDGES_MEV = 10.0 ** np.linspace(-6.0, 7.0, 651)
PHANTOM_ENERGIES_MEV = (
    PHANTOM_ENERGY_EDGES_MEV[:-1] + PHANTOM_ENERGY_EDGES_MEV[1:]
) / 2.0
PROFILE_MARKER_LIMIT = 50
MASS_FRACTION_PLOT_MINIMUM = 1.0e-12
LENGTH_TO_KM = {
    "mm": 1.0e-6,
    "cm": 1.0e-5,
    "m": 1.0e-3,
    "km": 1.0,
}
PARTICLE_NAMES = {
    22: "photon",
    2212: "proton",
    -2212: "antiproton",
    2112: "neutron",
    -2112: "antineutron",
    11: "electron",
    -11: "positron",
    13: "muon-",
    -13: "muon+",
    211: "pion+",
    -211: "pion-",
    111: "pion0",
    321: "kaon+",
    -321: "kaon-",
}
PARTICLE_SYMBOLS = {
    22: r"$\gamma$",
    2212: r"$p$",
    -2212: r"$\bar{p}$",
    2112: r"$n$",
    -2112: r"$\bar{n}$",
    11: r"$e^{-}$",
    -11: r"$e^{+}$",
    12: r"$\nu_e$",
    -12: r"$\bar{\nu}_e$",
    13: r"$\mu^{-}$",
    -13: r"$\mu^{+}$",
    14: r"$\nu_\mu$",
    -14: r"$\bar{\nu}_\mu$",
    15: r"$\tau^{-}$",
    -15: r"$\tau^{+}$",
    16: r"$\nu_\tau$",
    -16: r"$\bar{\nu}_\tau$",
    211: r"$\pi^{+}$",
    -211: r"$\pi^{-}$",
    111: r"$\pi^{0}$",
    321: r"$K^{+}$",
    -321: r"$K^{-}$",
}
ELEMENT_SYMBOLS = (
    "n",
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
)


def particle_name(pdg_code):
    if pdg_code in PARTICLE_NAMES:
        return PARTICLE_NAMES[pdg_code]
    absolute_code = abs(pdg_code)
    if absolute_code >= 1_000_000_000:
        atomic_number = (absolute_code // 10_000) % 1_000
        mass_number = (absolute_code // 10) % 1_000
        element = (
            ELEMENT_SYMBOLS[atomic_number]
            if atomic_number < len(ELEMENT_SYMBOLS)
            else "Z%i" % atomic_number
        )
        prefix = "anti-" if pdg_code < 0 else ""
        return "%s%s-%i" % (prefix, element, mass_number)
    return str(pdg_code)


def particle_symbol(pdg_code):
    if pdg_code in PARTICLE_SYMBOLS:
        return PARTICLE_SYMBOLS[pdg_code]
    absolute_code = abs(pdg_code)
    if absolute_code >= 1_000_000_000:
        atomic_number = (absolute_code // 10_000) % 1_000
        mass_number = (absolute_code // 10) % 1_000
        element = (
            ELEMENT_SYMBOLS[atomic_number]
            if atomic_number < len(ELEMENT_SYMBOLS)
            else "Z%i" % atomic_number
        )
        if pdg_code < 0:
            return r"$^{%i}\overline{\mathrm{%s}}$" % (
                mass_number,
                element,
            )
        return r"$^{%i}\mathrm{%s}$" % (mass_number, element)
    return str(pdg_code)


def _particle_groups(particle_codes):
    groups = ([], [])
    for index, code in enumerate(particle_codes):
        group = 1 if abs(code) >= 1_000_000_000 else 0
        groups[group].append(index)
    return groups


def read_macro(filename):
    settings = {}
    energy_points = []
    with Path(filename).open() as macro:
        for line in macro:
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            command = fields[0]
            values = fields[1:]
            if command == "/gps/hist/point":
                energy_points.append((float(values[0]), float(values[1])))
            else:
                settings[command] = " ".join(values)
    return settings, np.asarray(energy_points)


def read_atmosphere(filename):
    root = ElementTree.parse(filename).getroot()

    materials = {}
    for material in root.findall("./materials/material"):
        properties = {
            "state": material.get("state"),
            "fractions": {
                fraction.get("ref"): float(fraction.get("n"))
                for fraction in material.findall("fraction")
            },
        }
        for tag, name in (("D", "density"), ("T", "temperature"), ("P", "pressure")):
            value = material.find(tag)
            properties[name] = float(value.get("value")) if value is not None else np.nan
        materials[material.get("name")] = properties

    solids = {}
    for sphere in root.findall("./solids/sphere"):
        unit = sphere.get("lunit", "mm")
        if unit not in LENGTH_TO_KM:
            raise ValueError("Unsupported GDML length unit: " + unit)
        scale = LENGTH_TO_KM[unit]
        solids[sphere.get("name")] = (
            float(sphere.get("rmin")) * scale,
            float(sphere.get("rmax")) * scale,
        )

    layers = []
    for volume in root.findall("./structure/volume"):
        material_reference = volume.find("materialref")
        solid_reference = volume.find("solidref")
        if material_reference is None or solid_reference is None:
            continue
        material = materials.get(material_reference.get("ref"))
        radii = solids.get(solid_reference.get("ref"))
        if material is None or radii is None or material["state"] != "gas":
            continue
        layers.append(
            {
                "rmin": radii[0],
                "rmax": radii[1],
                **material,
            }
        )

    layers.sort(key=lambda layer: layer["rmin"])
    if not layers:
        raise ValueError("No gaseous atmospheric layers found in " + str(filename))
    surface_radius = layers[0]["rmin"]
    for layer in layers:
        layer["altitude"] = (
            (layer["rmin"] + layer["rmax"]) / 2.0 - surface_radius
        )
    return layers


def _setting(settings, command, default="not set"):
    return settings.get(command, default)


def _source_summary(settings):
    position = " ".join(
        part
        for part in (
            _setting(settings, "/gps/pos/type"),
            _setting(settings, "/gps/pos/shape", ""),
        )
        if part
    )
    radius = _setting(settings, "/gps/pos/radius")
    direction = _setting(settings, "/gps/ang/type")
    theta = "%s to %s" % (
        _setting(settings, "/gps/ang/mintheta"),
        _setting(settings, "/gps/ang/maxtheta"),
    )
    return "\n".join(
        (
            "Particle: " + _setting(settings, "/gps/particle"),
            "Position: " + position,
            "Radius: " + radius,
            "Direction: " + direction,
            "Theta: " + theta,
            "Particles per event: " + _setting(settings, "/gps/number"),
            "Events: " + _setting(settings, "/run/beamOn"),
            "Threads in macro: " + _setting(settings, "/run/numberOfThreads"),
            "Production cut: " + _setting(settings, "/run/setCut"),
            "Random seeds: " + _setting(settings, "/random/setSeeds"),
        )
    )


def _plot_profile(axis, values, altitudes, title, xlabel, logarithmic=False):
    marker = "o" if len(altitudes) <= PROFILE_MARKER_LIMIT else None
    axis.plot(values, altitudes, marker=marker)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Altitude [km]")
    if logarithmic and np.any(np.asarray(values) > 0):
        axis.set_xscale("log")
    axis.grid(alpha=0.25)


def plot_species_inputs(simname):
    settings, energy_points = read_macro(simname + ".mac")
    energy_bins = np.atleast_1d(np.loadtxt(simname + ".bins"))
    layers = read_atmosphere(simname + ".gdml")
    altitudes = np.array([layer["altitude"] for layer in layers])

    figure, axes = plt.subplots(ncols=3, nrows=2, figsize=(18, 10))
    species = simname.capitalize()

    if energy_points.size:
        axes[0, 0].stairs(
            energy_points[1:, 1],
            energy_points[:, 0],
            baseline=0.0,
            label="Macro weight",
        )
    axes[0, 0].plot(
        energy_bins,
        np.zeros(energy_bins.shape),
        linestyle="none",
        marker="|",
        markersize=10,
        label="Output energy bin",
    )
    axes[0, 0].set_title(species + " configured energies")
    axes[0, 0].set_xlabel("Primary kinetic energy [MeV]")
    axes[0, 0].set_ylabel("Configured weight")
    axes[0, 0].set_xscale("log")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.25)

    _plot_profile(
        axes[0, 1],
        [layer["density"] for layer in layers],
        altitudes,
        species + " atmospheric density",
        "Density [g/cm3]",
        logarithmic=True,
    )
    _plot_profile(
        axes[0, 2],
        [layer["pressure"] for layer in layers],
        altitudes,
        species + " atmospheric pressure",
        "Pressure [Pa]",
        logarithmic=True,
    )
    _plot_profile(
        axes[1, 0],
        [layer["temperature"] for layer in layers],
        altitudes,
        species + " atmospheric temperature",
        "Temperature [K]",
    )

    elements = sorted(
        {
            element
            for layer in layers
            for element in layer["fractions"]
        }
    )
    for element in elements:
        fractions = np.array(
            [layer["fractions"].get(element, 0.0) for layer in layers]
        )
        fractions[fractions < MASS_FRACTION_PLOT_MINIMUM] = np.nan
        marker = "o" if len(altitudes) <= PROFILE_MARKER_LIMIT else None
        axes[1, 1].plot(fractions, altitudes, marker=marker, label=element)
    axes[1, 1].set_title(species + " atmospheric composition")
    axes[1, 1].set_xlabel(
        "Mass fraction (values below %.0e omitted)" % MASS_FRACTION_PLOT_MINIMUM
    )
    axes[1, 1].set_ylabel("Altitude [km]")
    axes[1, 1].set_xscale("log")
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.25)

    axes[1, 2].axis("off")
    axes[1, 2].set_title(species + " source and run settings")
    axes[1, 2].text(
        0.0,
        1.0,
        _source_summary(settings),
        transform=axes[1, 2].transAxes,
        va="top",
        family="monospace",
    )

    figure.tight_layout()
    filename = simname + ".inputs.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename


def read_phantom_table(filename):
    with Path(filename).open() as phantom_file:
        particle_codes = np.fromstring(phantom_file.readline(), sep=" ", dtype=int)
    response = np.atleast_2d(np.loadtxt(filename, skiprows=1))
    if response.shape != (particle_codes.size, 650):
        raise ValueError(
            "%s has shape %s; expected (%i, 650)"
            % (filename, response.shape, particle_codes.size)
        )
    return particle_codes, response


def plot_phantom_inputs(phantom_id, phantom_name):
    radiation_codes, radiation = read_phantom_table(
        "radiation_phantom%i.txt" % phantom_id
    )
    counting_codes, counting = read_phantom_table(
        "counting_phantom%i.txt" % phantom_id
    )
    if not np.array_equal(radiation_codes, counting_codes):
        raise ValueError(
            "Radiation and counting particle codes differ for phantom %i"
            % phantom_id
        )

    groups = _particle_groups(radiation_codes)
    group_titles = ("Particles", "Nuclei")
    figure, axes = plt.subplots(
        ncols=2,
        nrows=2,
        figsize=(14, 10),
        sharex=True,
        sharey="row",
    )
    for column, (indices, group_title) in enumerate(zip(groups, group_titles)):
        colors = plt.get_cmap("turbo")(np.linspace(0.05, 0.95, len(indices)))
        count_axis = axes[0, column]
        radiation_axis = axes[1, column]
        count_axis.axhline(
            1.0,
            color="0.25",
            linestyle=":",
            linewidth=1.0,
            label="Perfect counting",
        )
        radiation_axis.plot(
            PHANTOM_ENERGIES_MEV,
            PHANTOM_ENERGIES_MEV,
            color="0.25",
            linestyle=":",
            linewidth=1.0,
            label="Full absorption",
        )
        for color, index in zip(colors, indices):
            label = particle_name(radiation_codes[index])
            count_axis.plot(
                PHANTOM_ENERGIES_MEV,
                np.where(counting[index] > 0, counting[index], np.nan),
                color=color,
                linewidth=1.0,
                label=label,
            )
            radiation_axis.plot(
                PHANTOM_ENERGIES_MEV,
                np.where(radiation[index] > 0, radiation[index], np.nan),
                color=color,
                linewidth=1.0,
                label=label,
            )

        count_axis.set_title(group_title)
        for axis in (count_axis, radiation_axis):
            axis.set_xscale("log")
            axis.set_yscale("log")
            axis.grid(alpha=0.25)
            axis.legend(fontsize=7, ncols=2)
        radiation_axis.set_xlabel("Incident particle energy [MeV]")

    axes[0, 0].set_ylabel("Counting efficiency")
    axes[1, 0].set_ylabel("Ionization response [MeV]")
    display_name = phantom_name or "Phantom %i" % phantom_id
    figure.suptitle(display_name)
    figure.tight_layout()
    if phantom_name:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", phantom_name)
        filename = "phantom.%s.inputs.png" % safe_name
    else:
        filename = "phantom-%i.inputs.png" % phantom_id
    figure.savefig(filename)
    plt.close(figure)
    return filename


def _input_phantom_ids():
    pattern = re.compile(r"^radiation_phantom(\d+)\.txt$")
    return sorted(
        int(match.group(1))
        for path in Path.cwd().iterdir()
        if (match := pattern.match(path.name)) is not None
    )


def plot_inputs():
    filenames = []
    errors = []
    for simname in ("protons", "alphas"):
        inputs = [
            Path(simname + extension)
            for extension in (".gdml", ".mac", ".bins")
        ]
        present = [path.is_file() for path in inputs]
        if any(present) and not all(present):
            missing = [str(path) for path, exists in zip(inputs, present) if not exists]
            errors.append(
                "%s inputs: missing %s" % (simname, ", ".join(missing))
            )
            continue
        if all(present):
            try:
                filenames.append(plot_species_inputs(simname))
            except Exception as error:
                errors.append("%s inputs: %s" % (simname, error))

    try:
        metadata = {
            phantom["id"]: phantom["stem"]
            for phantom in read_phantoms(Path.cwd())
        }
    except Exception as error:
        metadata = {}
        errors.append("phantom metadata: " + str(error))
    for phantom_id in _input_phantom_ids():
        counting = Path("counting_phantom%i.txt" % phantom_id)
        if not counting.is_file():
            errors.append("phantom %i inputs: missing %s" % (phantom_id, counting))
            continue
        phantom_name = metadata.get(phantom_id)
        try:
            filenames.append(plot_phantom_inputs(phantom_id, phantom_name))
        except Exception as error:
            errors.append("phantom %i inputs: %s" % (phantom_id, error))
    return filenames, errors
