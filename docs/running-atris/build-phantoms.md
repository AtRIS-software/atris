# Build a water-sphere phantom

A phantom response describes how a specified object responds to incident
particles. Create its run separately from the atmospheric simulation that will
use its tables. The builder currently accepts an unshielded liquid-water sphere
and the particle species you select; it does not assume an incident spectrum.

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
prepare its build. This writes configuration only; no transport starts.

```python
from pathlib import Path
from atris_tools.psf import build_psf, write_psf
from atris_tools.phantom_builder import PhantomBuild
from atris_tools.particles import ion_pdg

sphere = build_psf(
    inner_radius_km=[0], outer_radius_km=[15.0 / 1e5],
    temperature_k=293, density_g_cm3=0.997, pressure_pa=101325,
    mass_fractions={"H": 2 * 1.00794 / 18.01528,
                    "O": 15.9994 / 18.01528},
    solid_composition="H112O888", state="liquid",
)
write_psf("water.psf", sphere)
build = PhantomBuild.prepare(
    Path.cwd(), "water.psf", [22, 2212, ion_pdg(26, 56), ion_pdg(28, 58)],
    stem="water-sphere",
    pilot_events=1300, relative_tolerance=0.05,
    absolute_dose_tolerance_Gy=1e-12, confidence_factor=1.96,
)
```

This example selects photons, protons, iron-56 and nickel-58. Add PDG codes of other species
you need; keep photon 22 first for response-table export. The API adds vacuum
termination shells and converts the PSF to GDML for each batch. Geometry,
production cuts, physics list, and precision settings are fixed for a build.
Changing them requires a separate run directory, not overwriting completed work.

## Run small batches

Still inside `water-phantom`, run one initial batch for each selected species:

```bash
atris-build-phantom . --batches 4 --threads 1
```

Each initial batch samples the full 650-bin energy grid. These small pilots
populate the histograms; they do not establish a finished calibration. The
command returns after the requested number of batches and refreshes exports.
Choose thread counts for your hardware and workload; no default is a measured
optimum. Both `atris-run` and the native `AtRIS` executable must be on `PATH`.

## Refine and inspect

Request another bounded set of batches using the adaptive selector:

```bash
atris-build-phantom . --adaptive --batches 5 --threads 1
```

The selector works on species/energy decades, not species totals. It explores
unresolved ranges and ranges without matching-thread timing measurements before
comparing predicted precision gains per wall second. Once those measurements
exist, every fifth selection revisits the least recently sampled unfinished
range. This keeps coverage visible rather than spending every batch on a single
apparently productive range. Forecasts use previous matching batch wall times,
including launch overhead; a detected clock gap excludes that timing from fits.
Forecasts are estimates, not measured benefits of changing the worker count.

The mean deposited-energy fraction is

$$
\hat f = \left\langle \frac{W}{K}\right\rangle,
$$

where $W$ is deposited ionizing energy and $K$ is incident kinetic energy.
For bin-centre kinetic energy $K$ and sphere mass $m$, the builder estimates
$\hat D = K\hat f/m$ after converting energy to joules and mass to kilograms.
The corresponding standard error is $\sigma_D = K\sigma_f/m$. This conversion
uses the bin centre, not the individually sampled primary energies.

A resolved bin passes when

$$
z\sigma_D \leq \max(a, r|\hat D|).
$$

Here `confidence_factor` is $z$, `absolute_dose_tolerance_Gy` is $a$, and
`relative_tolerance` is $r$. The example uses $z=1.96$, $a=10^{-12}$ Gy and
$r=0.05$. These are explicit example settings, not recommended universal
precision requirements. At least two samples, a finite standard error and a
positive estimated response are required. An empirical zero remains unresolved;
it is not evidence of an exactly zero response. Pass counts can decrease when
new samples change the estimated mean or variance.

Counting efficiency is recorded for primaries with positive deposited energy.
It is shown in the response tables but does not drive this selector. Completion
requires every energy bin of every selected species to meet the dose criterion.
This describes sampling precision, not uncertainty in the physical model.

Refresh plots without launching transport:

```bash
atris-build-phantom . --postprocess-only
```

`export/diagnostics.png` shows a curve per species: mean fraction above and
relative standard error below. Dose-per-primary guides in the upper row use
this sphere's mass; the lower guides show relative precision. Curves omit bins
without a positive resolved estimate. `export/sampling-precision.png` shows
relative and absolute dose standard errors on the full species/bin grid.
`export/sampling-state.json` gives coverage and precision counts.
These are creation diagnostics. The regular `atris-plot` response figure instead
shows counting efficiency and mean fraction with deposited-energy guides.

## Resume and export

`batches.json` records each selection, its forecast and measured wall time.
Each batch keeps its macros, seeds, ROOT output and saved `COMPLETE` marker.
Only completed chunks contribute to statistics. A second builder in the same
directory is rejected by a process lock on Linux and macOS.

After an interruption, repeat the batch command. The pending batch is resumed
first with unchanged inputs and seeds; partial output is moved into a timestamped
`interrupted-*` directory before rerunning. Completed batches are not repeated.
This costs the unfinished batch's work, not the completed results. A quiet log
or buffered ROOT file alone does not establish a stalled transport process.

Partial exports retain missing estimates as NaN, along with sample counts and
uncertainties in the sampling NPZ. They are not loadable response tables until
every coefficient is finite. Before staging, inspect both the exported arrays
and `sampling-state.json`; finite estimates alone do not establish precision
completion. For using complete tables, see
[phantom selection and staging](prepare-simulation.md#optionally-select-phantoms).
