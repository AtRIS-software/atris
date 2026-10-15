"""Create quick-look plots of the files supplied to AtRIS."""

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import FixedLocator
import numpy as np

from .atrismacrogen import read_macro
from .phantoms import read_phantoms
from .psf import read_psf_layers
from .phantom_tables import PhantomTable, ENERGY_EDGES_MEV, ENERGY_CENTRES_MEV
from .particles import (
    ION_PDG_BASE, ELEMENT_ATOMIC_NUMBERS, ELEMENT_SYMBOLS,
    PARTICLE_NAMES, PARTICLE_SYMBOLS, particle_name, particle_symbol,
)


PHANTOM_ENERGY_EDGES_MEV = ENERGY_EDGES_MEV
PHANTOM_ENERGIES_MEV = ENERGY_CENTRES_MEV
MASS_FRACTION_PLOT_MINIMUM = 1.0e-12
LENGTH_TO_KM = {
    "mm": 1.0e-6,
    "cm": 1.0e-5,
    "m": 1.0e-3,
    "km": 1.0,
}


def log_norm(data):
    positive = data[np.isfinite(data) & (data > 0)]
    if not positive.size:
        return None
    return LogNorm(vmin=np.min(positive), vmax=np.max(positive))


def positive_log_edges(values, bins=80):
    values = np.asarray(values)
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




def element_label(reference):
    """Return a chemical symbol without Geant4's built-in name prefix."""
    return reference.removeprefix("G4_")


def element_sort_key(reference):
    """Order recognized elements by atomic number, then custom references."""
    label = element_label(reference)
    return (ELEMENT_ATOMIC_NUMBERS.get(label, float("inf")), label)


def _particle_groups(particle_codes):
    groups = ([], [])
    for index, code in enumerate(particle_codes):
        group = 1 if abs(code) >= ION_PDG_BASE else 0
        groups[group].append(index)
    return groups


def read_layers(filename):
    """Read every sensitive spherical layer from a GDML geometry."""
    root = ElementTree.parse(filename).getroot()

    materials = {
        material.get("name"): material
        for material in root.findall("./materials/material")
    }

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
        sensitive_detector = volume.find("auxiliary[@auxtype='SensDet']")
        if (
            material_reference is None
            or solid_reference is None
            or sensitive_detector is None
        ):
            continue
        material = materials[material_reference.get("ref")]
        radii = solids[solid_reference.get("ref")]
        properties = {
            "state": material.get("state"),
            "fractions": {
                fraction.get("ref"): float(fraction.get("n"))
                for fraction in material.findall("fraction")
            },
            "density": float(material.find("D").get("value")),
            "temperature": float(material.find("T").get("value")),
            "pressure": float(material.find("P").get("value")),
        }
        layers.append(
            {
                "rmin": radii[0],
                "rmax": radii[1],
                "detector_id": int(sensitive_detector.get("auxvalue")),
                **properties,
            }
        )

    layers.sort(key=lambda layer: layer["rmin"])
    if not layers:
        raise ValueError("No sensitive spherical layers found in " + str(filename))
    return layers


def surface_radius(layers):
    """Return the outer radius of the contiguous solid planetary body."""
    all_layers = sorted(layers, key=lambda layer: layer["rmin"])
    radius = all_layers[0]["rmax"]
    for layer in all_layers[1:]:
        if layer["state"] != "solid" or not np.isclose(
            layer["rmin"], radius, rtol=0.0, atol=1.0e-9
        ):
            break
        radius = layer["rmax"]
    return radius


def non_termination_layers(layers):
    """Return every modeled shell between AtRIS's two termination volumes."""
    outer_termination_id = max(layer["detector_id"] for layer in layers)
    return [
        layer
        for layer in layers
        if layer["detector_id"] not in (0, outer_termination_id)
    ]


def shell_coordinates(
    layers, detector_ids=None, location="center", reference_radius=None
):
    """Calculate signed physical coordinates for detector shells."""
    radius = (
        surface_radius(layers)
        if reference_radius is None
        else reference_radius
    )

    if detector_ids is not None:
        by_id = {layer["detector_id"]: layer for layer in layers}
        layers = [by_id[int(detector_id)] for detector_id in detector_ids]

    detector_ids = np.array([layer["detector_id"] for layer in layers])
    distance_min = np.array([layer["rmin"] - radius for layer in layers])
    distance_max = np.array([layer["rmax"] - radius for layer in layers])
    if location == "center":
        positions = (distance_min + distance_max) / 2.0
        edges = np.array([distance_min[0]] + list(distance_max))
    elif location == "outer":
        positions = distance_max
        if positions.size == 1:
            width = max(abs(positions[0]) * 0.05, 1.0)
            edges = np.array([positions[0] - width, positions[0] + width])
        else:
            midpoints = (positions[:-1] + positions[1:]) / 2.0
            edges = np.concatenate(
                (
                    [positions[0] - (midpoints[0] - positions[0])],
                    midpoints,
                    [positions[-1] + (positions[-1] - midpoints[-1])],
                )
            )
    else:
        raise ValueError("Unknown shell location: " + location)
    return detector_ids, positions, edges


def model_shell_edges(layers):
    """Return the distance bounds of the model between termination shells."""
    radius = surface_radius(layers)
    _, _, edges = shell_coordinates(
        non_termination_layers(layers),
        reference_radius=radius,
    )
    return edges


def setup_shell_axis(axis):
    """Format a vertical distance-from-surface axis."""
    axis.set_ylabel("Distance from surface [km]")
    axis.set_yscale("linear")
    axis.minorticks_on()


def _source_summary(settings, layers, energy_count):
    position = " ".join(
        part
        for part in (
            settings.get("/gps/pos/type", "not set"),
            settings.get("/gps/pos/shape", ""),
        )
        if part
    )
    radius = settings.get("/gps/pos/radius", "not set")
    direction = settings.get("/gps/ang/type", "not set")
    if position == "Surface Sphere" and direction == "cos":
        direction = "inward cosine law"
    theta = "%s to %s" % (
        settings.get("/gps/ang/mintheta", "not set"),
        settings.get("/gps/ang/maxtheta", "not set"),
    )
    lines = [
        "Particle: " + settings.get("/gps/particle", "not set"),
        "Position: " + position,
    ]

    radius_fields = settings.get("/gps/pos/radius", "").split()
    radius_km = None
    if len(radius_fields) == 2 and radius_fields[1] in LENGTH_TO_KM:
        radius_km = float(radius_fields[0]) * LENGTH_TO_KM[radius_fields[1]]
    if radius_km is not None:
        planet_radius_km = surface_radius(layers)
        lines.append("Planet surface radius: %.3f km" % planet_radius_km)
        modeled_layers = non_termination_layers(layers)
        if modeled_layers:
            model_radius_km = max(layer["rmax"] for layer in modeled_layers)
            lines.append(
                "Modeled shell outer radius: %.3f km" % model_radius_km,
            )
            lines.append("Modeled layers: %i" % len(modeled_layers))
        lines.extend(
            (
                "Source sphere radius: " + radius,
                "Altitude above surface: %.3f km"
                % (radius_km - planet_radius_km),
            )
        )
        if modeled_layers:
            clearance_m = (radius_km - model_radius_km) * 1000
            lines.append("Model clearance: %.3f m" % clearance_m)
    else:
        lines.append("Source sphere radius: " + radius)

    lines.append("Configured energies: %i" % energy_count)
    lines.extend(
        (
            "Direction: " + direction,
            "Incidence angle: " + theta,
            "Particles per event: " + settings.get("/gps/number", "not set"),
            "Events: " + settings.get("/run/beamOn", "not set"),
            "Threads in macro: " + settings.get("/run/numberOfThreads", "not set"),
            "Secondary production range cut: "
            + settings.get("/run/setCut", "not set"),
            "Random seeds: " + settings.get("/random/setSeeds", "not set"),
        )
    )
    return "\n".join(lines)


def mark_model_regions(axis, edges):
    """Draw model boundaries and lock the distance axis before plotting data."""
    for edge in (edges[0], edges[-1]):
        axis.axhline(edge, color="black", zorder=10)
    lower_limit, upper_limit = axis.get_ylim()
    axis.set_ylim((lower_limit, upper_limit))
    for y, label in (
        ((lower_limit + edges[0]) / 2.0, "Ground"),
        ((edges[-1] + upper_limit) / 2.0, "Space"),
    ):
        axis.text(
            0.5,
            y,
            label,
            transform=axis.get_yaxis_transform(),
            ha="center",
            va="center",
            zorder=10,
        )


def _plot_shell_profiles(
    axis,
    temperature_axis,
    density,
    pressure,
    temperature,
    edges,
    model_edges,
):
    mark_model_regions(temperature_axis, model_edges)
    density_curve = axis.stairs(
        density,
        edges,
        orientation="horizontal",
        color="C0",
    )
    pressure_curve = axis.stairs(
        pressure,
        edges,
        orientation="horizontal",
        color="C1",
    )
    temperature_curve = temperature_axis.stairs(
        temperature,
        edges,
        orientation="horizontal",
        color="C2",
    )
    setup_shell_axis(axis)
    axis.set_xlabel("Density [g/cm3] and pressure [Pa]")
    temperature_axis.set_xlabel("Temperature [K]")
    if np.any(np.asarray(density) > 0) or np.any(np.asarray(pressure) > 0):
        axis.set_xscale("log")
    temperature_axis.minorticks_on()
    axis.grid(alpha=0.25)
    temperature_axis.legend(
        [density_curve, pressure_curve, temperature_curve],
        ["Density", "Pressure", "Temperature"],
    )


def _plot_composition(axis, layers, edges, model_edges):
    mark_model_regions(axis, model_edges)
    elements = sorted(
        {
            element
            for layer in layers
            for element in layer["fractions"]
        },
        key=element_sort_key,
    )
    for element in elements:
        label = element_label(element)
        fractions = np.array(
            [layer["fractions"].get(element, 0.0) for layer in layers]
        )
        fractions[fractions < MASS_FRACTION_PLOT_MINIMUM] = np.nan
        curve = axis.stairs(
            fractions,
            edges,
            orientation="horizontal",
            label=label,
        )
        modeled = np.flatnonzero(
            np.isfinite(fractions)
            & (edges[:-1] >= model_edges[0])
            & (edges[1:] <= model_edges[-1])
        )
        if modeled.size >= 3:
            index = modeled[modeled.size // 2]
            axis.annotate(
                label,
                (fractions[index], (edges[index] + edges[index + 1]) / 2.0),
                xytext=(4, 0),
                textcoords="offset points",
                color=curve.get_edgecolor(),
                fontsize=8,
                va="center",
            )
    axis.tick_params(axis="y", labelleft=False)
    axis.set_xlabel(
        "Mass fraction (values below %.0e omitted)" % MASS_FRACTION_PLOT_MINIMUM
    )
    axis.set_xscale("log")
    axis.minorticks_on()
    axis.legend()
    axis.grid(alpha=0.25)


def plot_psf_inputs(filename="simulation.psf"):
    """Plot the planetary layers defined by a PSF file."""
    path = Path(filename)
    layers = read_psf_layers(path)
    radius = surface_radius(layers)
    model_edges = model_shell_edges(layers)
    _, _, edges = shell_coordinates(layers, reference_radius=radius)
    figure, axes = plt.subplots(
        ncols=2,
        figsize=(12, 10),
        sharey=True,
    )
    figure.suptitle("Planet specification inputs")
    _plot_shell_profiles(
        axes[0],
        axes[0].twiny(),
        [layer["density"] for layer in layers],
        [layer["pressure"] for layer in layers],
        [layer["temperature"] for layer in layers],
        edges,
        model_edges,
    )
    _plot_composition(axes[1], layers, edges, model_edges)
    figure.tight_layout()
    output_path = path.with_name(path.name + ".png")
    figure.savefig(output_path)
    plt.close(figure)
    return output_path.name


def plot_species_inputs(simname):
    settings, energy_points = read_macro(simname + ".mac")
    energy_bins = np.atleast_1d(np.loadtxt(simname + ".bins"))
    geometry_layers = read_layers(simname + ".gdml")

    figure, (settings_axis, energy_axis) = plt.subplots(
        ncols=2,
        figsize=(14, 6),
    )
    species = simname.capitalize()
    figure.suptitle(species + " simulation inputs")

    if energy_points.size:
        energy_axis.bar(
            energy_points[:-1, 0],
            energy_points[1:, 1],
            width=np.diff(energy_points[:, 0]),
            align="edge",
            alpha=0.25,
            edgecolor="C0",
            linewidth=0.5,
        )
    energy_axis.set_title("Configured energies")
    energy_axis.set_xlabel("Primary kinetic energy [MeV]")
    energy_axis.set_ylabel("Configured weight")
    energy_axis.set_xscale("log")
    energy_axis.minorticks_on()
    energy_axis.grid(alpha=0.25)

    settings_axis.axis("off")
    settings_axis.set_title("Source and run settings")
    settings_axis.text(
        0.0,
        1.0,
        _source_summary(settings, geometry_layers, energy_bins.size),
        transform=settings_axis.transAxes,
        va="top",
        family="monospace",
    )

    figure.tight_layout()
    filename = simname + ".inputs.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename


def plot_phantom_inputs(phantom_id, phantom_name, *, tables=None):
    """Plot counting and energy retention, one row per available response."""
    if tables is None:
        tables = {
            prefix: PhantomTable.read(path, counting=prefix == "counting")
            for prefix in ("counting", "radiation")
            if (path := Path("%s_phantom%i.txt" % (prefix, phantom_id))).is_file()
        }
    rows = [(prefix, tables[prefix]) for prefix in ("counting", "radiation") if prefix in tables]
    if not rows:
        raise ValueError("No phantom response tables available")
    codes = np.array(list(dict.fromkeys(int(code) for _, table in rows for code in table.pdg_codes)))
    groups = _particle_groups(codes)
    group_titles = ("Particles", "Nuclei")
    figure, axes = plt.subplots(
        ncols=2,
        nrows=len(rows),
        figsize=(16, 9) if len(rows) == 1 else (16, 12),
        sharex=True,
        sharey="row",
        squeeze=False,
    )
    for column, (indices, group_title) in enumerate(zip(groups, group_titles)):
        if column == 0:
            colors = plt.get_cmap("tab20")(np.arange(len(indices)) % 20)
        else:
            colors = plt.get_cmap("turbo")(np.linspace(0.05, 0.95, len(indices)))
        for color, index in zip(colors, indices):
            code = codes[index]
            label = particle_symbol(code)
            if abs(code) < ION_PDG_BASE:
                name = "pion" if code == 111 else particle_name(code).rstrip("+-")
                label += " " + name
            for row, (prefix, table) in enumerate(rows):
                matches = np.flatnonzero(table.pdg_codes == code)
                if not matches.size:
                    continue
                values = table.coefficients[matches[0]]
                axes[row, column].plot(
                    PHANTOM_ENERGIES_MEV,
                    values if prefix == "counting" else np.where(values > 0, values, np.nan),
                    color=color, linewidth=1.0, label=label,
                )

    # Finish plotting both species groups before fixing shared axis limits.
    for column, group_title in enumerate(group_titles):
        axes[0, column].set_title(group_title)
        for row, (prefix, _) in enumerate(rows):
            axis = axes[row, column]
            axis.set_xscale("log")
            if prefix == "radiation":
                axis.set_yscale("log")
            axis.grid(alpha=0.25)
            if prefix == "radiation":
                lower, upper = axis.get_ylim()
                first_power = 2 * int(np.floor(np.log10(lower) / 2))
                last_power = 2 * int(np.ceil(np.log10(upper) / 2))
                axis.yaxis.set_major_locator(
                    FixedLocator(10.0 ** np.arange(first_power, last_power + 1, 2))
                )
                xlimits = axis.get_xlim()
                for exponent in (-3, 0, 3, 6):
                    energy = 10.0 ** exponent
                    label_y = energy / xlimits[1]
                    if not lower < label_y < upper:
                        continue
                    guide_x = np.asarray(xlimits)
                    axis.plot(guide_x, energy / guide_x, color="0.25",
                              linestyle=":", linewidth=1.0, zorder=0)
                    if column == 1:
                        axis.text(1.01, label_y, rf"$10^{{{exponent}}}$ MeV",
                                  transform=axis.get_yaxis_transform(),
                                  ha="left", va="center", clip_on=False)
                axis.set_xlim(xlimits)
                axis.set_ylim(lower, upper)
                axis.axhline(1.0, color="black", linestyle="-", linewidth=1.0, zorder=0)
            if column == 0:
                axis.set_ylabel("Counting efficiency" if prefix == "counting"
                                else r"Mean deposited-energy fraction $\langle W/K\rangle$")
        axes[-1, column].set_xlabel(r"Incident kinetic energy $K$ (MeV)")
    display_name = phantom_name or "Phantom %i" % phantom_id
    figure.suptitle(display_name + " | Phantom response")
    legend_top = 0.14 if len(rows) == 1 else 0.10
    figure.tight_layout(rect=(0, 0.17 if len(rows) == 1 else 0.13, .96, 0.97))
    for column, indices in enumerate(groups):
        if not indices:
            continue
        axis = axes[0, column]
        position = axis.get_position()
        entries = {}
        for row_axis in axes[:, column]:
            handles, labels = row_axis.get_legend_handles_labels()
            entries.update(zip(labels, handles))
        axis.legend(
            list(entries.values()), list(entries),
            fontsize=9,
            ncols=min(len(indices), 4 if column == 0 else 8),
            loc="upper center" if column == 0 else "upper left",
            bbox_to_anchor=(position.x0 + position.width / 2, legend_top)
            if column == 0 else (position.x0, legend_top, position.width, 0),
            bbox_transform=figure.transFigure,
            mode=None if column == 0 else "expand",
            columnspacing=2.5 if column == 0 else 1.0,
            handletextpad=0.8,
            borderaxespad=0,
            frameon=False,
        )
    if phantom_name:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", phantom_name)
        filename = "phantom.%s.inputs.png" % safe_name
    else:
        filename = "phantom-%i.inputs.png" % phantom_id
    figure.savefig(filename)
    plt.close(figure)
    return filename


def _input_phantom_ids():
    pattern = re.compile(r"^(?:radiation|counting)_phantom(\d+)\.txt$")
    return sorted(
        {int(match.group(1))
        for path in Path.cwd().iterdir()
        if (match := pattern.match(path.name)) is not None}
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

    psf_path = Path("simulation.psf")
    if psf_path.is_file():
        try:
            filenames.append(plot_psf_inputs(psf_path))
        except Exception as error:
            errors.append("simulation PSF: %s" % error)

    try:
        metadata = {
            phantom["id"]: phantom["stem"]
            for phantom in read_phantoms(Path.cwd())
        }
    except Exception as error:
        metadata = {}
        errors.append("phantom metadata: " + str(error))
    for phantom_id in _input_phantom_ids():
        phantom_name = metadata.get(phantom_id)
        tables = {}
        for prefix in ("radiation", "counting"):
            if not Path("%s_phantom%i.txt" % (prefix, phantom_id)).is_file():
                continue
            try:
                tables[prefix] = PhantomTable.read(
                    "%s_phantom%i.txt" % (prefix, phantom_id), counting=prefix == "counting"
                )
            except Exception as error:
                errors.append("phantom %i %s inputs: %s" % (phantom_id, prefix, error))
        if tables:
            try:
                filenames.append(plot_phantom_inputs(phantom_id, phantom_name, tables=tables))
            except Exception as error:
                errors.append("phantom %i inputs: %s" % (phantom_id, error))
    return filenames, errors
