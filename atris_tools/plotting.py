"""Create quick-look PDF plots from processed AtRIS response data."""

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


def make_allplots(data, xbins, geometry, simname, nphant):
    ybins = (geometry["inn_surface/cm2"] / (4.0 * np.pi)) ** 0.5 / 100000.0
    ybins = ybins - ybins[2]
    altitude_edges = np.empty(ybins.size + 1)
    altitude_edges[1:-1] = (ybins[:-1] + ybins[1:]) / 2
    altitude_edges[0] = ybins[0] - (ybins[1] - ybins[0]) / 2
    altitude_edges[-1] = ybins[-1] + (ybins[-1] - ybins[-2]) / 2
    titles = ["Ionization", "Absorbed dose", "Dose equivalent", "Count rate"]
    figure, all_axes = plt.subplots(
        ncols=4,
        figsize=(16, 5 * nphant),
        nrows=nphant,
        sharey=True,
        squeeze=False,
    )
    for phantom_index in range(nphant):
        axes = all_axes[phantom_index]
        data_indices = [
            3,
            4 + phantom_index * 3,
            5 + phantom_index * 3,
            6 + phantom_index * 3,
        ]
        for index, data_index in enumerate(data_indices):
            histogram = data[data_index]
            positive = histogram[np.isfinite(histogram) & (histogram > 0)]
            norm = (
                LogNorm(vmin=np.min(positive), vmax=np.max(positive))
                if positive.size
                else None
            )
            axis = axes[index]
            mesh = axis.pcolormesh(
                xbins,
                altitude_edges,
                histogram,
                norm=norm,
                shading="flat",
                rasterized=True,
            )
            axis.set_title(simname.capitalize() + " " + titles[index])
            axis.set_xlabel("Primary kinetic energy [MeV]")
            axis.set_xscale("log")
            figure.colorbar(mesh, ax=axis, label="Response per primary")
            axis.set_ylim(0, ybins[-2])
        axes[0].set_ylabel("Altitude [km]\nPhantom %i" % phantom_index)
    figure.tight_layout()
    figure.savefig(simname + ".pdf")
    plt.close(figure)
