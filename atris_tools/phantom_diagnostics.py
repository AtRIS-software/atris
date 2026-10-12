"""Sampling diagnostics for creation, separate from staged response plots."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from .input_plotting import _particle_groups
from .particles import ION_PDG_BASE, particle_name, particle_symbol
from .phantom_calibration import RESPONSE_ENERGY_EDGES_MEV


def plot_creation_diagnostics(response, path):
    """Plot retained fraction, relative SE, and both sampling-quality metrics.

    Errors are one standard error. Log plots omit unresolved and zero errors;
    retained arrays are not filtered or modified by these display choices.
    """
    path = Path(path)
    edges = RESPONSE_ENERGY_EDGES_MEV
    centres = (edges[:-1] + edges[1:]) / 2
    fraction = response.energy_fraction
    error = response.fraction_standard_error
    valid = (response.sample_counts > 1) & np.isfinite(error) & (fraction > 0)
    relative = np.divide(error, fraction, out=np.full_like(error, np.nan), where=valid)
    dose_error = error * centres * 1.602176634e-13 / (response.mass_g * 1e-3)
    groups = _particle_groups(response.pdg_codes)
    figure, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True, sharey="row")
    labels = []
    for code in response.pdg_codes:
        label = particle_symbol(code)
        if abs(code) < ION_PDG_BASE:
            label += " " + ("pion" if code == 111 else particle_name(code).rstrip("+-"))
        labels.append(label)
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
        dose_factor = xlimits[1] * 1.602176634e-13 / (response.mass_g * 1e-3)
        first = 2 * int(np.ceil(np.log10(ylimits[0] * dose_factor) / 2))
        last = 2 * int(np.floor(np.log10(ylimits[1] * dose_factor) / 2))
        for exponent in range(first, last + 1, 2):
            coefficient = 10.0 ** exponent * response.mass_g * 1e-3 / 1.602176634e-13
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
    axes[1, 0].set_ylabel(r"Relative uncertainty $\sigma_{\hat f}/|\hat f|$")
    figure.suptitle("Phantom creation diagnostics | dose guides: Gy per incident primary")
    figure.tight_layout(rect=(0, .13, .96, .97))
    for column, indices in enumerate(groups):
        if not indices:
            continue
        axis = axes[0, column]
        position = axis.get_position()
        axis.legend(fontsize=9, ncols=min(len(indices), 4 if column == 0 else 8),
                    loc="upper center" if column == 0 else "upper left",
                    bbox_to_anchor=(position.x0 + position.width / 2, .10) if column == 0
                    else (position.x0, .10, position.width, 0), bbox_transform=figure.transFigure,
                    mode=None if column == 0 else "expand", columnspacing=2.5 if column == 0 else 1,
                    handletextpad=.8, borderaxespad=0, frameon=False)
    figure.text(.5, .012, "One standard error; dose uses bin centres. Lower uncertainty limit: 1st percentile; unresolved/zero errors omitted.",
                ha="center", fontsize=8)
    figure.savefig(path)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(15, max(4, len(labels) * .25)), sharey=True)
    cmap = plt.get_cmap("Blues").copy()
    cmap.set_bad("0.85")
    for axis, values, title in zip(axes, (relative, dose_error),
            (r"Relative standard error $\sigma_{\hat f}/|\hat f|$",
             r"Absolute dose standard error $\sigma_{\hat D}$ (Gy per primary)")):
        finite = valid & np.isfinite(values) & (values > 0)
        positive = values[finite]
        lower, upper = (float(positive.min()), float(positive.max())) if positive.size else (1e-3, 1)
        if lower == upper:
            upper = lower * 10
        mesh = axis.pcolormesh(edges, np.arange(len(labels) + 1),
                              np.ma.masked_where(~finite, values), cmap=cmap,
                              norm=LogNorm(lower, upper), shading="flat")
        axis.set_xscale("log")
        axis.set_xlabel(r"Incident kinetic energy $K$ (MeV)")
        axis.set_title(title)
        figure.colorbar(mesh, ax=axis)
    axes[0].set_yticks(np.arange(len(labels)) + .5, labels)
    axes[0].invert_yaxis()
    figure.suptitle("Sampling precision | grey: unresolved or zero estimated error")
    figure.tight_layout()
    figure.savefig(path.with_name("sampling-precision.png"))
    plt.close(figure)
