"""Shared plotting coordinates, scales and species groups."""

from matplotlib.colors import LogNorm
import numpy as np

from .particles import ION_PDG_BASE


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


def particle_groups(particle_codes):
    groups = ([], [])
    for index, code in enumerate(particle_codes):
        group = 1 if abs(code) >= ION_PDG_BASE else 0
        groups[group].append(index)
    return groups


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
