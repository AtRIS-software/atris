# Build a water-sphere phantom

A phantom response describes how a specified object responds to incident
particles. Response generation has a separate run directory from the atmospheric
simulation that uses its tables. The builder accepts spherical PSF layers,
preserves their materials, and calculates the response of the innermost layer
for each selected incident species. Outer layers provide passive shielding:
they affect transport but are excluded from detector deposits and mass.
This example uses a homogeneous liquid-water sphere without shielding.

For a small worked example with saved results, see
[View notebook](../tutorials/water-phantom.ipynb), located at
`docs/tutorials/water-phantom.ipynb`, or download
{download}`water-phantom.ipynb <../tutorials/water-phantom.ipynb>`.

## Prepare the run

Install the Python tools and make the native executable available as described
in [installation](installation.md). The recommended layout keeps `runs/` beside
AtRIS. Starting inside your `runs/` directory:

```bash
mkdir water-phantom
cd water-phantom
```

In a Python session in that directory, describe the physical sphere in PSF and
prepare the sampling configuration. Transport starts with the batch command below.

```python
from atris_tools.psf import PSF
from atris_tools.phantom_builder import PhantomBuilder

hydrogen_molar_mass = 1.00794
oxygen_molar_mass = 15.9994
water_molar_mass = 2 * hydrogen_molar_mass + oxygen_molar_mass
water_mass_fractions = {
    "H": 2 * hydrogen_molar_mass / water_molar_mass,
    "O": oxygen_molar_mass / water_molar_mass,
}
sphere = PSF(
    inner_radius_km=0, outer_radius_km=1.5e-4,
    temperature_k=293, density_g_cm3=0.997, pressure_pa=101325,
    mass_fractions=water_mass_fractions,
    state="liquid",
)
print(sphere)
species = ["photon", "proton", "iron-56", "nickel-58"]
builder = PhantomBuilder(
    sphere, species,
    name="water-sphere",
    pilot_events=1300, dose_rtol=0.05,
    dose_atol_Gy=1e-12, confidence_factor=1.96,
)
print(builder)
schedule = builder.show_schedule(batches=4, adaptive=True)
```

`builder.show_schedule(...)` prints a preview of upcoming batches with species,
incident kinetic-energy ranges, primary counts, and selection reasons. It is
available immediately after preparation. The requested batches are predicted
from the current statistics, tracking previewed visits in memory. With
`adaptive=True`, actual choices are recalculated after each completed batch.
An interrupted batch appears first, marked for resumption. Once all configured
precision targets pass, the adaptive preview has no further batches to select.

The call also returns a tuple of `Batch` records. Each record exposes `species`,
`energy_range_MeV` (a two-element NumPy array), `events`, `reason`,
`forecast_seconds` (`None` without a timing estimate), and `status` (`planned`
or `resume`). Both `show_schedule()` and `run()` default to one batch.

The reason identifies the selection:

| Reason | Selection |
| --- | --- |
| `initial coverage` | First full-range batch for a species |
| `insufficient samples` | A bin has fewer than two primaries |
| `unresolved uncertainty` | A bin's estimated standard error is nonfinite |
| `zero deposit` | Samples exist, but a bin's estimated mean deposit is zero |
| `timing pilot` | The range lacks a usable focused-batch timing at the selected thread count |
| `coverage` | Periodic revisit to a less recently sampled range |
| `precision` | Predicted uncertainty reduction per second |
| `batch count` | Full-range repeat to reach the requested batch count, with adaptive scheduling disabled |

When several exploration conditions apply, the first applicable reason in this
table is shown. The selected batch samples the entire energy decade.

This example selects photons, protons, iron-56 and nickel-58. Add PDG codes of other species
you need; keep photon 22 first for response-table export. The API adds vacuum
termination shells and converts the PSF to GDML for each batch. Geometry,
production cuts, physics list, and precision settings are fixed for a build.
Each physical setup has its own run directory and retained results.

`simulation.psf` is the geometry and material input. The builder reads its
radius, density, temperature, pressure, and composition directly. JSON files retain
sampling settings and batch history. The generated `phantom.psf` adds the
transport shells while preserving the physical water layer.

## Production cuts and phantom size

`production_cut_mm` sets a range cut in millimetres. Geant4 converts it into
secondary-production energy thresholds for each material. For processes using
these cuts, lower energy transfers contribute to local deposition, while higher
transfers create secondary tracks. Smaller cuts generally resolve more secondary
transport and require more computation. The [Geant4 physics manual](https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/electromagnetic/energy_loss/setcuts.html)
describes the conversion.

The relevant geometric scale is the distance over which transport changes the
scored deposit, especially near the phantom boundary. A secondary created near
that boundary can carry energy out of the phantom. Replacing its transport with
local deposition can therefore change the response. The example's 0.1 mm cut
is small compared with a 150 mm radius, but exceeds the radius of a 4 micrometre
sphere and is twice the radius of a 50 micrometre sphere.

A cut-convergence comparison uses the same geometry, physics and incident
species at progressively smaller cuts, with each setup in its own run directory.
Agreement of the response curves within their sampling uncertainties establishes
a suitable cut for that calculation. A small cut relative to the radius is a
useful starting point; the comparison measures its adequacy. More primaries
reduce sampling uncertainty, while this comparison tests the transport
approximation.

## Run small batches

`PhantomBuilder(...)` saves the sampling settings in the run folder.
`atris-build-phantom` opens a `PhantomBuilder` from those saved settings and
calls its `run()` method. Python and the terminal command use the same builder;
the folder carries its configuration and batch history between sessions.

Still inside `water-phantom`, run one initial batch for each selected species:

```bash
atris-build-phantom . --adaptive --batches 4 --threads 1
```

Each initial batch samples the full 650-bin energy grid. These small pilots
populate the histograms and provide initial estimates. Further batches refine
their precision. The
command returns after the requested number of batches and refreshes exports.
Suitable thread counts depend on the hardware and workload. The launcher uses
`atris-run` and the native executable available on `PATH`.

## Refine and inspect

Request another bounded set of batches using the adaptive selector:

```bash
atris-build-phantom . --adaptive --batches 5 --threads 1
```

The selector works on individual species/energy decades. It first measures
unresolved ranges and ranges needing matching-thread timing measurements, then
comparing predicted precision gains per wall second. Once those measurements
exist, every fifth selection revisits the least recently sampled unfinished
range. This balances coverage with predicted precision gains. Forecasts use previous matching batch wall times,
including launch overhead; a detected clock gap excludes that timing from fits.
They estimate the duration of a future batch at the recorded worker count.

The mean deposited-energy fraction is

$$
\left\langle \frac{W}{K}\right\rangle,
$$

where $W$ is deposited ionizing energy and $K$ is incident kinetic energy.
For bin-centre kinetic energy $K$ and sphere mass $m$, the builder estimates
$\hat D = K\langle W/K\rangle/m$ after converting energy to joules and mass to kilograms.
The corresponding standard error is $\sigma_D = K\sigma_{\langle W/K\rangle}/m$. This conversion
uses the arithmetic energy-bin centre.

A resolved bin passes when

$$
z\sigma_D \leq \max(a, r|\hat D|).
$$

Here `confidence_factor` is $z$, `dose_atol_Gy` is $a$, and
`dose_rtol` is $r$. The example uses $z=1.96$, $a=10^{-12}$ Gy and
$r=0.05$. The precision settings are adjustable for the intended calculation.
At least two samples, a finite standard error and a positive estimated response
are required. A bin with zero observed deposition remains unresolved.
Pass counts can decrease when
new samples change the estimated mean or variance.

Counting efficiency is recorded for primaries with positive deposited energy.
The selector uses energy-response uncertainty. Completion
requires every energy bin of every selected species to meet the dose criterion.
The criterion measures Monte Carlo sampling precision.

The following command refreshes plots from completed statistics:

```bash
atris-build-phantom . --postprocess-only
```

`water-sphere_diagnostics.png` shows a curve per species: mean fraction above and
relative standard error below. Dose-per-primary guides in the upper row use
this sphere's mass; the lower guides show relative precision. Curves omit bins
without a positive resolved estimate. `water-sphere_sampling-precision.png` shows
relative and absolute dose standard errors on the full species/bin grid.
`water-sphere_sampling-state.json` gives coverage and precision counts.
These are creation diagnostics. The regular `atris-plot` response figure
shows counting efficiency and mean fraction with deposited-energy guides.

## Resume and export

`batches.json` records each selection, its forecast and measured wall time.
With `builder.run(time_limit_s=60)`, each batch has a one-minute event-loop
budget. Refinement learns throughput from the actual completed primaries,
including time-shortened batches. Matching species, energy ranges and thread
counts provide the timing measurements. Predicted uncertainty reduction uses
the primaries expected within the budget; runtime includes measured launch and
output overhead. `builder.show_schedule(time_limit_s=60, adaptive=True)` previews
selection with the same budget.
Each batch keeps its macros, seeds, ROOT output and saved `COMPLETE` marker.
Only completed chunks contribute to statistics. A second builder in the same
directory is rejected by a process lock on Linux and macOS.

After an interruption, repeat the batch command. The pending batch is resumed
first with unchanged inputs and seeds; partial output is moved into a timestamped
`interrupted-*` directory before rerunning. Completed batches remain available
and contribute to the cumulative statistics. Recovery repeats the unfinished
batch. Process CPU activity and saved completion markers show transport progress;
logs and ROOT output can be buffered during a batch.

Partial exports retain missing estimates as NaN, along with sample counts and
uncertainties in `water-sphere_sampling.root`. Loadable response tables have
finite coefficients throughout. The exported arrays and `water-sphere_sampling-state.json`
report coverage and progress toward the chosen precision target.
The procedure for using completed tables is
[phantom selection and staging](prepare-simulation.md#optionally-select-phantoms).

`builder.gather()` combines that build's completed chunks into a `Phantom`,
using its saved name, geometry and sampling settings. It runs no transport.
After restarting Python, reopen the run with `PhantomBuilder.open(".")`.
Saving the phantom's sampling ROOT file preserves these settings,
geometry, arrays and uncertainties. Reading that file restores the same data model:

```python
from atris_tools.phantom import Phantom

phantom = Phantom.read_root("water-sphere_sampling.root")
counts = phantom.sample_counts
fraction = phantom.energy_fraction
standard_error = phantom.fraction_standard_error
quality = phantom.precision()
comparison = phantom.precision(relative_dose_tolerance=0.01)
```

`precision()` uses the stored target unless individual settings are overridden.
The comparison does not change the saved settings. Without stored settings,
supply all three arguments: `relative_dose_tolerance`,
`absolute_dose_tolerance_Gy`, and `confidence_factor`.

The gathered phantom saves its own data. Plotting functions accept Matplotlib
axes and return them, so figure layout, styling and saving remain familiar:

```python
import matplotlib.pyplot as plt
from atris_tools.phantom_builder import PhantomBuilder
from atris_tools.phantom_plotting import plot_creation_diagnostics

builder = PhantomBuilder.open(".")
phantom = builder.gather()
paths = phantom.save()
figure, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True, sharey="row")
plot_creation_diagnostics(phantom, axes=axes)
figure.subplots_adjust(bottom=0.2, right=0.9, hspace=0.15)
figure.savefig("water-sphere_diagnostics.png")
plt.show()
```

`paths` contains the response table, counting table, sampling ROOT and, when
written, precision-state JSON paths. It can be ignored when not needed. Saving
does not create or change `phantoms.txt`; use the separate
[selection and staging procedure](prepare-simulation.md#optionally-select-phantoms)
to choose phantoms for a simulation.

`plot_sampling_precision(phantom, axes=axes)` draws a 2x2 map figure: relative
and absolute dose standard errors above, incident and counted primaries per
energy bin below. The count maps share a colour scale and include zero counts.
With axes omitted, either plotting function creates a figure
with its default layout.

See [sampling ROOT exports](../reference/outputs.md#phantom-sampling-root-exports)
for the stored arrays, units, and metadata.
