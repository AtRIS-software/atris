"""Sampling diagnostics for creation, separate from staged response plots."""

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
import numpy as np

from .input_plotting import _particle_groups
from .particles import ION_PDG_BASE, particle_name, particle_symbol
from .phantom import RESPONSE_ENERGY_EDGES_MEV, JOULES_PER_MEV, KG_PER_GRAM


def _sampling_values(response):
    edges = RESPONSE_ENERGY_EDGES_MEV
    centres = (edges[:-1] + edges[1:]) / 2
    fraction = response.energy_fraction
    error = response.fraction_standard_error
    valid = (response.sample_counts > 1) & np.isfinite(error) & (fraction > 0)
    relative = np.divide(error, fraction, out=np.full_like(error, np.nan), where=valid)
    dose_error = error * response.dose_per_fraction_Gy
    labels = []
    for code in response.pdg_codes:
        label = particle_symbol(code)
        if abs(code) < ION_PDG_BASE:
            label += " " + ("pion" if code == 111 else particle_name(code).rstrip("+-"))
        labels.append(label)
    return centres, fraction, relative, dose_error, valid, labels


def _plot_axes(axes, shape, **kwargs):
    if axes is None:
        figure, axes = plt.subplots(*shape, **kwargs)
        return figure, axes, True
    axes = np.asarray(axes, dtype=object)
    if axes.shape != shape:
        raise ValueError(f"Expected axes with shape {shape}")
    figure = axes.flat[0].figure
    if any(axis.figure is not figure for axis in axes.flat):
        raise ValueError("All axes must belong to the same figure")
    return figure, axes, False


def plot_creation_diagnostics(phantom, axes=None):
    """Draw fraction and relative-error curves on a 2-by-2 axes array.

    Create axes when omitted and return them for further Matplotlib styling.
    Errors are one standard error; logarithmic curves omit unresolved or zero
    values. Saving and displaying the figure are handled by the caller.
    """
    centres, fraction, relative, _, _, labels = _sampling_values(phantom)
    groups = _particle_groups(phantom.pdg_codes)
    figure, axes, created = _plot_axes(axes, (2, 2), figsize=(16, 12),
                                     sharex=True, sharey="row")
    for column, indices in enumerate(groups):
        colors = (plt.get_cmap("tab20")(np.arange(len(indices)) % 20) if column == 0
                  else plt.get_cmap("turbo")(np.linspace(.05, .95, len(indices))))
        for index, color in zip(indices, colors):
            for row, values in enumerate((fraction, relative)):
                axes[row, column].plot(centres, np.where(values[index] > 0, values[index], np.nan),
                                       color=color, linewidth=1, label=labels[index])
        axes[0, column].set_title(("Particles", "Nuclei")[column])
        for axis in axes[:, column]:
            axis.set_xscale("log")
            axis.set_yscale("log")
            axis.grid(alpha=.25)
        axes[1, column].set_xlabel(r"Incident kinetic energy $K$ (MeV)")
    positive = relative[np.isfinite(relative) & (relative > 0)]
    if not np.any(np.isfinite(fraction) & (fraction > 0)):
        axes[0, 0].set_ylim(.1, 10)
    if positive.size:
        axes[1, 0].set_ylim(bottom=np.percentile(positive, 1))
    else:
        axes[1, 0].set_ylim(1e-4, 1)
    # Establish common row limits before adding guides in either column.
    for column in range(2):
        axis = axes[0, column]
        xlimits, ylimits = axis.get_xlim(), axis.get_ylim()
        dose_factor = xlimits[1] * JOULES_PER_MEV / (phantom.mass_g * KG_PER_GRAM)
        first = 2 * int(np.ceil(np.log10(ylimits[0] * dose_factor) / 2))
        last = 2 * int(np.floor(np.log10(ylimits[1] * dose_factor) / 2))
        for exponent in range(first, last + 1, 2):
            coefficient = 10.0 ** exponent * phantom.mass_g * KG_PER_GRAM / JOULES_PER_MEV
            axis.plot(xlimits, coefficient / np.asarray(xlimits), color="0.25",
                      linestyle=":", linewidth=1, zorder=0)
            value = coefficient / xlimits[1]
            if column == 1 and ylimits[0] < value < ylimits[1]:
                axis.text(1.01, value, rf"$10^{{{exponent}}}$ Gy", transform=axis.get_yaxis_transform(),
                          clip_on=False, va="center")
        axis.set_xlim(xlimits)
        axis.set_ylim(ylimits)
        axis.axhline(1, color="black", linewidth=1, zorder=0)
        axis = axes[1, column]
        ylimits = axis.get_ylim()
        for value, label in ((.1, "10%"), (.01, "1%"), (.001, "0.1%"), (.0001, "0.01%")):
            if ylimits[0] < value < ylimits[1]:
                axis.axhline(value, color="0.25", linestyle=":", linewidth=1, zorder=0)
                if column == 1:
                    axis.text(1.01, value, label, transform=axis.get_yaxis_transform(),
                              clip_on=False, va="center")
        axis.set_ylim(ylimits)
    axes[0, 0].set_ylabel(r"Mean deposited ionizing-energy fraction $\langle W/K\rangle$")
    axes[1, 0].set_ylabel(r"Relative uncertainty $\sigma_{\langle W/K\rangle}/|\langle W/K\rangle|$")
    if created:
        figure.suptitle("Phantom creation diagnostics | dose guides: Gy per incident primary")
        figure.tight_layout(rect=(0, .13, .96, .97))
    for column, indices in enumerate(groups):
        if not indices:
            continue
        axis = axes[0, column]
        position = axis.get_position()
        if not created:
            axes[1, column].legend(fontsize=9, ncols=min(len(indices), 4 if column == 0 else 8),
                                   loc="upper center", bbox_to_anchor=(.5, -.25), frameon=False,
                                   columnspacing=2.5 if column == 0 else 1, handletextpad=.8)
            continue
        axis.legend(fontsize=9, ncols=min(len(indices), 4 if column == 0 else 8),
                    loc="upper center" if column == 0 else "upper left",
                    bbox_to_anchor=(position.x0 + position.width / 2, .10) if column == 0
                    else (position.x0, .10, position.width, 0), bbox_transform=figure.transFigure,
                    mode=None if column == 0 else "expand", columnspacing=2.5 if column == 0 else 1,
                    handletextpad=.8, borderaxespad=0, frameon=False)
    if created:
        figure.text(.5, .012, "One standard error; dose uses bin centres. Lower uncertainty limit: 1st percentile; unresolved/zero errors omitted.",
                    ha="center", fontsize=8)
    return axes


def plot_sampling_precision(phantom, axes=None, *, relative_target=.01):
    """Draw uncertainty and primary-count maps on a 2-by-2 axes array.

    The top row shows relative and absolute dose standard errors. The bottom
    shows sampled and counted primaries per bin on a shared logarithmic scale.
    Zero counts and unresolved uncertainty estimates are masked.
    The relative-error scale extends two decades below relative_target.
    """
    if not np.isfinite(relative_target) or relative_target <= 0:
        raise ValueError("relative_target must be finite and positive")
    _, _, relative, dose_error, valid, labels = _sampling_values(phantom)
    edges = RESPONSE_ENERGY_EDGES_MEV
    if axes is None:
        figure, axes = plt.subplots(2, 2, figsize=(15, max(9, len(labels) * .5)), sharey=True)
        created = True
    else:
        figure, axes, created = _plot_axes(axes, (2, 2))
    cmap = LinearSegmentedColormap.from_list(
        "uncertainty", ["#2468b4", "#79509b", "#d43b32"])
    cmap.set_bad("0.65")
    cmap.set_over(cmap(1.))
    count_cmap = plt.get_cmap("Oranges").copy()
    count_cmap.set_bad("0.65")
    count_max = max(10, int(phantom.sample_counts.max()))
    count_norm = LogNorm(vmin=1, vmax=count_max)
    for index, (axis, values, title) in enumerate(zip(axes.flat,
            (relative, dose_error, phantom.sample_counts, phantom.detected_counts),
            (r"Relative standard error $\sigma_{\langle W/K\rangle}/|\langle W/K\rangle|$",
             r"Absolute dose standard error $\sigma_{\hat D}$ (Gy per primary)",
             "Incident primaries per energy bin", "Counted primaries per energy bin"))):
        if index < 2:
            finite = valid & np.isfinite(values) & (values > 0)
            positive = values[finite]
            lower, upper = (float(positive.min()), float(positive.max())) if positive.size else (1e-3, 1)
            if index == 0:
                lower = relative_target / 100
                upper = max(upper, relative_target)
            elif positive.size:
                lower = float(np.percentile(positive, 1))
            if lower == upper:
                upper = lower * 10
            data = np.ma.masked_where(~finite, values)
            norm = LogNorm(lower, upper)
        else:
            data, norm = np.ma.masked_less_equal(values, 0), count_norm
        mesh = axis.pcolormesh(edges, np.arange(len(labels) + 1),
                              data, cmap=cmap if index < 2 else count_cmap,
                              norm=norm, shading="flat")
        axis.set_xscale("log")
        axis.set_xlabel(r"Incident kinetic energy $K$ (MeV)")
        axis.set_title(title)
        if index < 2:
            colorbar = figure.colorbar(mesh, ax=axis, extend="both")
        else:
            figure.colorbar(mesh, ax=axis)
    axes[0, 0].set_yticks(np.arange(len(labels)) + .5, labels)
    for axis in axes.flat:
        axis.set_ylim(len(labels), 0)
    if created:
        figure.suptitle("Sampling precision and primary counts")
        figure.tight_layout()
    return axes
