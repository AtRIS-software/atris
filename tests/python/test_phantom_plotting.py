import matplotlib.pyplot as plt
import numpy as np
import pytest

from atris_tools.phantom import Phantom
from atris_tools.phantom_statistics import PhantomStatistics
from atris_tools.phantom_plotting import plot_creation_diagnostics, plot_sampling_precision
from atris_tools.psf import PSF


@pytest.fixture
def phantom():
    statistics = {
        code: PhantomStatistics(np.full(650, 10), np.full(650, .5),
                                np.full(650, .1), np.full(650, 5))
        for code in (22, 1000260560)
    }
    geometry = PSF(inner_radius_km=0, outer_radius_km=15 / 1e5,
                   temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                   mass_fractions={"H": 2 * 1.00794 / 18.01528, "O": 15.9994 / 18.01528}, state="liquid")
    return Phantom.from_statistics(statistics, name="water-sphere", geometry=geometry)


@pytest.mark.parametrize("plot,shape", [
    (plot_creation_diagnostics, (2, 2)), (plot_sampling_precision, (2, 2)),
])
def test_plots_draw_on_supplied_axes_and_leave_figure_open(phantom, plot, shape, tmp_path):
    figure, axes = plt.subplots(*shape, figsize=(12, 9))
    figure.suptitle("User's title")
    positions = [axis.get_position().bounds for axis in axes.flat]
    original = phantom.energy_fraction.copy()
    returned = plot(phantom, axes=axes)
    assert all(a is b for a, b in zip(returned.flat, axes.flat))
    assert plt.fignum_exists(figure.number)
    assert figure._suptitle.get_text() == "User's title"
    if plot is plot_creation_diagnostics:
        assert positions == [axis.get_position().bounds for axis in axes.flat]
    np.testing.assert_array_equal(phantom.energy_fraction, original)
    path = tmp_path / "custom.png"
    figure.savefig(path)
    assert path.stat().st_size > 0
    plt.close(figure)


@pytest.mark.parametrize("plot,shape", [
    (plot_creation_diagnostics, (2, 2)), (plot_sampling_precision, (2, 2)),
])
def test_plots_create_and_return_axes(phantom, plot, shape):
    axes = plot(phantom)
    assert axes.shape == shape
    assert plt.fignum_exists(axes.flat[0].figure.number)
    plt.close(axes.flat[0].figure)


def test_curve_plot_rejects_wrong_axes_shape(phantom):
    figure, axes = plt.subplots(1, 2)
    with pytest.raises(ValueError, match="shape"):
        plot_creation_diagnostics(phantom, axes=axes)
    plt.close(figure)


def test_count_maps_include_zero_counts_and_zero_deposit_bins(phantom):
    phantom.sample_counts[0, 0] = 0
    phantom.counting_efficiency[0, 0] = np.nan
    phantom.energy_fraction[0, 1] = 0
    phantom.counting_efficiency[0, 1] = 0
    counts = phantom.sample_counts.copy()
    axes = plot_sampling_precision(phantom)
    incident = axes[1, 0].collections[0]
    counted = axes[1, 1].collections[0]
    np.testing.assert_array_equal(incident.get_array().reshape(counts.shape).filled(0), counts)
    np.testing.assert_array_equal(counted.get_array().reshape(counts.shape).filled(0), phantom.detected_counts)
    np.testing.assert_array_equal(np.ma.getmaskarray(incident.get_array()).reshape(counts.shape), counts == 0)
    np.testing.assert_array_equal(np.ma.getmaskarray(counted.get_array()).reshape(counts.shape), phantom.detected_counts == 0)
    assert incident.norm is counted.norm
    assert incident.cmap.name == counted.cmap.name == "Oranges"
    cmap = axes[0, 0].collections[0].cmap
    assert cmap.name == "uncertainty"
    assert cmap(0.)[2] > cmap(0.)[0]
    assert cmap(1.)[0] > cmap(1.)[2]
    assert np.max(cmap(np.linspace(0, 1, 256))[:, :3]) < .9
    np.testing.assert_array_equal(cmap.get_over(), cmap(1.))
    assert not np.array_equal(cmap.get_bad(), cmap(1.))
    assert incident.norm.vmin == 1
    assert incident.norm(np.sqrt(incident.norm.vmax)) == pytest.approx(.5)
    assert phantom.detected_counts[0, 0] == 0
    assert phantom.detected_counts[0, 1] == 0
    assert np.ma.getmaskarray(axes[0, 0].collections[0].get_array()).reshape(counts.shape)[0, 1]
    np.testing.assert_array_equal(phantom.sample_counts, counts)
    plt.close(axes[0, 0].figure)


def test_sampling_plot_rejects_wrong_axes_shape(phantom):
    figure, axes = plt.subplots(1, 2)
    with pytest.raises(ValueError, match="shape"):
        plot_sampling_precision(phantom, axes=axes)
    plt.close(figure)


def test_relative_scale_extends_two_decades_below_reference(phantom):
    axes = plot_sampling_precision(phantom)
    mesh = axes[0, 0].collections[0]
    assert mesh.norm.vmin == pytest.approx(1e-4)
    assert mesh.norm.vmax == pytest.approx(mesh.get_array().max())
    assert mesh.colorbar.extend == "both"
    plt.close(axes[0, 0].figure)


def test_absolute_scale_trims_low_tail(phantom):
    phantom.fraction_standard_error[0, 0] *= 1e-12
    axes = plot_sampling_precision(phantom)
    mesh = axes[0, 1].collections[0]
    values = mesh.get_array().compressed()
    assert mesh.norm.vmin == pytest.approx(np.percentile(values, 1), rel=1e-12, abs=0)
    assert mesh.norm.vmin > values.min()
    assert mesh.colorbar.extend == "both"
    plt.close(axes[0, 0].figure)
