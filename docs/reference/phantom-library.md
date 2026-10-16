# Phantom library

The `phantoms/` directory contains precomputed response and counting tables.
Its top-level radiation-response files store energy fractions, compatible with
the C++ reader and scorer. Deposited-energy response files are in
`phantoms/MeV-valued/`; counting tables remain at the top level.
Choose the phantom material, geometry, shielding, and threshold that match the
quantity you want to estimate. The tables describe a response to the transported
particle field; [phantom responses](../background/radiation-quantities.md#phantom-responses)
explains their physical role.

[Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622) describes how
phantom energy-response tables are calculated and used during atmospheric
transport. It also explains the choice of a 15 cm radius water sphere and
compares calculated doses with balloon measurements. The supplied library
includes later additions, described in the historical notes below.

To calculate a response yourself, use the Jupyter notebook at
`docs/tutorials/water-phantom.ipynb`:
[View notebook](../tutorials/water-phantom.ipynb) or download
{download}`water-phantom.ipynb <../tutorials/water-phantom.ipynb>`.
It defines a water sphere with `PSF`, selects incident species, and prepares
sampling with `PhantomBuilder`. The notebook runs a small batch group from Python,
then gathers the phantom and plots its response and sampling precision. Follow
[building phantoms](../running-atris/build-phantoms.md) for your own run.

## Water-sphere phantoms

The four water-sphere phantom runs have the following physical settings,
recorded in their retained exports. The names identify sphere sizes.
All four are homogeneous, unshielded liquid water with density
$0.997\,\mathrm{g\,cm^{-3}}$.

| Run name | Radius | Mass (g) | AtRIS effective area (cm²) | Production cut (mm) |
| --- | --- | --- | --- | --- |
| `bacteria-water-r4um` | 4 µm | 2.672783e-10 | 1.005310e-6 | 1e-5 |
| `cell-water-r50um` | 50 µm | 5.220280e-7 | 1.570796e-4 | 1e-5 |
| `small-bug-water-r1mm` | 1 mm | 4.176224e-3 | 6.283185e-2 | 1e-5 |
| `icru-water-r15cm` | 15 cm | 1.409476e4 | 1.413717e3 | 1e-1 |

Mass is $4\pi r^3\rho/3$. AtRIS effective area is $2\pi r^2$, reflecting
the two-direction interface-crossing normalization; projected disk area is
$\pi r^2$. All four exports cover 44 incident species on 650 kinetic-energy
bins from 1 eV to 10 TeV and record `FTFP_BERT_HP`. Counting requires a strictly
positive ionizing deposit. The production cut controls secondary production.
The generated tables are stored in each run's exports. Sampling diagnostics
record their coverage and precision.

The response includes the primary and secondary ionizing deposits in the water
volume and includes zero-deposit primaries in its mean. Scoring covers the
water volume. Sphere symmetry relates the projected-disk beam to incident
directions for these unshielded spheres. Missing species, unsampled bins, and
bins needing further precision are incomplete sampling results.
The
[ROOT contents and scope](outputs.md#phantom-sampling-root-exports) for the
compact metadata fields and [building phantoms](../running-atris/build-phantoms.md)
for precision diagnostics.

## Legacy phantom properties

These are the supplied historical families, separate from the four phantom
runs above. Unknown entries identify historical settings whose values remain
unrecovered. Reconstruction candidates are listed separately from recorded properties.

| Family | Recorded geometry/material | Mass (g) | AtRIS area (cm²) | Response values in `phantoms/` |
| --- | --- | --- | --- | --- |
| `icru_*_old_response.txt` | 15 cm radius water sphere, according to the historical notes | 1.4094755e4 | 1.41372e3 | Energy fraction; no energy scaling |
| `ramona_*_old_response.txt` | Silicon detector A; radius 14.85 mm, thickness 0.315 mm | 5.082e-1 | 6.928 | Energy fraction; no energy scaling |
| `bact_zero_0.000MeV_response.txt` | Original specification unrecovered; 4 µm water sphere is a reconstruction candidate | Unknown | Unknown | Energy fraction; no energy scaling |
| `cell_zero_0.000MeV_response.txt` | 50 µm water-sphere reconstruction recipe; full historical settings unrecovered | Unknown | Unknown | Energy fraction; no energy scaling |
| `sbug_zero_0.000MeV_response.txt` | Original specification unrecovered; 1 mm water sphere is a reconstruction candidate | Unknown | Unknown | Energy fraction; no energy scaling |
| `flatramona_*`, `randramona_*`, `realramona_*` legacy responses | Variant geometries and source settings unrecovered | Unknown | Unknown | `_old_response.txt` files are energy fractions; no energy scaling |

The listed RAMONA and ICRU masses and areas are the historical scoring-volume
values used by the Earth example, not the mass or area of added aluminium
shielding. Original production cuts and sampling uncertainties are not established
by these dimensions. `zero`, `five`, `ten`, `fifteen`, `twenty`, and `twentyfive`
denote nominal aluminium shielding thicknesses of 0, 5, 10, 15, 20, and 25 mm.
Availability depends on the family; filename threshold labels are not reliable
descriptions of all legacy energy responses. See
[known discrepancies](../known-bugs.md#differences-between-old-and-new-phantom-tables).

## Moved deposited-energy tables

The unsuffixed radiation-response tables moved to `phantoms/MeV-valued/`
contain deposited energy in MeV. AtRIS consumes the corresponding energy
fractions. Their companion counting and variance files remain in `phantoms/`.

| Moved family | Response files | Nominal shielding (mm Al) | Filename thresholds (MeV) | Required response scaling |
| --- | --- | --- | --- | --- |
| `icru_*_response.txt` | 5 | 0, 5, 10, 15, 20 | 0.000 | Divide each column by its $K$ in MeV |
| `ramona_*_response.txt` | 10 | 0, 5, 10, 15, 20 | 0.000, 0.060 | Divide each column by its $K$ in MeV |
| `flatramona_*_response.txt` | 5 | 0, 5, 10, 15, 20 | 0.060 | Divide each column by its $K$ in MeV |
| `randramona_*_response.txt` | 12 | 0, 5, 10, 15, 20, 25 | 0.000, 0.060 | Divide each column by its $K$ in MeV |
| `realramona_*_response.txt` | 5 | 0, 5, 10, 15, 20 | 0.060 | Divide each column by its $K$ in MeV |

For stored deposited energy $W$ and energy-bin centre $K$, the converted
coefficient is

$$
f = \frac{W\;[\mathrm{MeV}]}{K\;[\mathrm{MeV}]}.
$$

The conversion uses arithmetic centres of the fixed edges:
$K_i=(K_{i,\mathrm{lower}}+K_{i,\mathrm{upper}})/2$.
`ENERGY_CENTRES_MEV` supplies these 650 values. Each species row is divided by
this centre vector, column by column. $K$ is total kinetic energy for every
species, including nuclei. Both $W$ and $K$ are expressed in MeV, and the
conversion factor varies with energy. Counting efficiencies are already
dimensionless. If a companion contains variance of $W$
in MeV², its fraction variance is obtained by division by $K^2$; a standard
error in MeV is divided by $K$. The companion's stored quantity and units
determine its conversion.

For example, in a Python session in your run directory, with `ATRIS_ROOT`
identifying the installation:

```python
import os
from pathlib import Path
from atris_tools.phantom_table import PhantomTable, ENERGY_CENTRES_MEV

source = Path(os.environ["ATRIS_ROOT"]) / "phantoms" / "MeV-valued" / "icru_zero_0.000MeV_detAB_response.txt"
table = PhantomTable.read(source)  # Coefficients retain the stored values.
table.coefficients /= ENERGY_CENTRES_MEV[None, :]
table.metadata.update(source_file=source.name, source_quantity="deposited_energy_MeV",
                      conversion="W_MeV / arithmetic_bin_centre_MeV")
table.write("icru-converted_response.txt")
```

The example writes a separate energy-fraction file. Its corresponding counting
table and documented mass and area complete the inputs for staging.
The conversion represents each energy column by its arithmetic bin centre;
an event-level mean of $W/K$ requires individual-event records. Historical
generation settings remain partly unrecovered, and differences between ICRU
datasets are described in the known discrepancies. C++ and Python readers
load the stored coefficients; the example performs the conversion explicitly.

## Existing Earth example

The Earth example uses the original, unshielded RAMONA and ICRU tables:

| ID | Phantom | Energy-fraction response | Counting efficiency |
| --- | --- | --- | --- |
| 0 | RAMONA/DOSTEL silicon detector A | `ramona_zero_0.060MeV_detA_old_response.txt` | `ramona_zero_0.060MeV_detA_counting.txt` |
| 1 | ICRU water sphere | `icru_zero_0.000MeV_detAB_old_response.txt` | `icru_zero_0.000MeV_detAB_counting.txt` |

RAMONA has radius 14.85 mm, thickness 0.315 mm, mass 0.5082 g, and area
6.928 cm²; its counting threshold is 0.060 MeV. The water sphere has radius
15 cm, mass 14094.7550 g, and effective area 1413.72 cm².

The `_old_counting.txt` filenames are symbolic links to the supplied counting
files, allowing staging with the `_old` stems. The numerical tables are
unchanged. The ICRU response and threshold differences remain documented in the
[known phantom-table discrepancies](../known-bugs.md#differences-between-old-and-new-phantom-tables).

The historical ICRU and RAMONA families also have response/counting pairs with the shielding labels
`five`, `ten`, `fifteen`, and `twenty` for 5, 10, 15, and 20 mm of aluminium.
RAMONA pairs are supplied for both `0.000MeV` and `0.060MeV` thresholds;
the ICRU pairs use `0.000MeV`. Other variants and historical files are also
present in the archive. Establish their geometry and normalization before
substituting them for the documented examples.

To use these tables, follow [phantom selection and staging](../running-atris/prepare-simulation.md#optionally-select-phantoms).
The [Earth preparation tutorial](../tutorials/earth-nrlmsis-full.md#prepare-the-phantom-inputs)
shows the two-phantom example. See the [selection-file format](inputs.md#phantom-selection)
and [response-matrix format](inputs.md#phantom-response-matrices) for the data definitions.

## Python tools

`PSF(...)`, `PSF.from_layers(...)`, `PSF.read(...)` and saving share the same
table-format checks: dimensions, agreement with material columns, finite values,
integer detector IDs and valid material-state codes. `psf.validate()` applies
these checks after direct array edits and returns the object. This does not
require full-sphere geometry; the phantom builder checks that requirement.

`atris_tools.particles` provides the particle identifiers and source settings
used by the phantom-generation tools and plot labels:

```python
from atris_tools.particles import pdg_code, ion_pdg, ion_numbers, particle_source, particle_name

pdg_code("electron")          # 11; Geant4's "e-" also works
ion_pdg(6, 12)                # 1000060120: ground-state carbon-12
ion_numbers(1000060120)       # (6, 12): atomic number and mass number
particle_name(1000060120)     # "C-12"
particle_source(1000060120)   # {"particle": "ion", "ion": {"Z": 6, "A": 12, "charge": 6}}
```

Pass `**particle_source(pdg)` to `prepare_phantom_batch` in
`atris_tools.phantom`. Named particles include antiparticles and
the light nuclei `deuteron`, `triton`, `He3`, and `alpha`. Other positive
ground-state nuclei use an ion source; they are fully stripped unless
`particle_source` receives an explicit `charge`. The charge state does not
change the PDG code. Excited states, hypernuclei, and generic antinuclear
sources are outside this helper's scope.

`prepare_phantom_batch` writes geometry and chunk inputs from the supplied PSF;
`gather_phantom_events` reads completed chunks into NumPy arrays;
`PhantomBuilder.gather()` combines its completed batches into fixed-grid responses
and sampling errors. Its `Phantom.save` method writes the response and counting
tables and sampling ROOT arrays with metadata, returning a tuple of the paths
written: response table, counting table, sampling ROOT, then precision-state JSON
when available. Existing files with this name are replaced. Saving never creates
or changes `phantoms.txt`; choosing simulation inputs is a separate
[selection and staging step](../running-atris/prepare-simulation.md#optionally-select-phantoms).
Read that ROOT
export with `Phantom.read_root(path)` to restore the response model,
including counts and uncertainties. The object exposes `name`, `geometry` (a
`PSF`), and `precision_settings` (`DosePrecision`) as explicit fields. Builder configuration uses
`builder.settings` with named attributes such as `stem` and `production_cut_mm`.
`phantom.metadata` contains supplementary provenance, including the original run
configuration. That configuration does not control calculations on the gathered response.
`phantom.precision()` uses `precision_settings` by default. Individual keyword
overrides (`relative_dose_tolerance`, `absolute_dose_tolerance_Gy`,
`confidence_factor`) affect only that calculation. Without saved settings,
all three must be supplied. The returned dictionary contains the NumPy arrays
`dose`, `dose_error`, `ratio`, `resolved` and `passed`.
Detector radii, density, mass, and source radius are derived from `geometry`;
they are not separately stored object state. The ROOT reader checks the file's
recorded derived quantities against its retained PSF.
Geometry comes from the retained PSF,
not the batch configuration JSON. Partial exports retain unsampled bins as
missing values; `allow_partial=False` requires complete coverage.
The [notebook](../tutorials/water-phantom.ipynb)
shows both source setups and the complete export workflow.

`builder.show_schedule(batches=1, ...)` prints the preview and returns a tuple
of `Batch` records, shared with batch execution. They expose `pdg`, `species`,
`energy_range_MeV`, `events`, `reason`, `forecast_seconds`, and `status`.
The status is `resume` for a pending batch and `planned` for a new selection;
the forecast is `None` without usable timing data. Previewing does not change
saved batch state. Adaptive execution recalculates choices after each batch.

Generated tables contain short `#` headers identifying their values and ROOT
companion; detailed scientific metadata lives in ROOT. See
[response-table headers](inputs.md#phantom-response-matrices).
The C++ reader skips all comments and reads coefficients unchanged.

`compact_phantom_chunk(path)` retains the per-primary energy sums,
histograms and metadata needed to reconstruct response statistics, while removing detailed
transport-step and interface-crossing records. It verifies the event arrays
before replacing the generated chunk file and records the discarded ntuples
in that file. `gather_phantom_events` reads either representation.
The `shower` output mode retains individual events for exploring counting
thresholds. The builder uses `phantom` output mode, which stores per-bin
statistics with a zero counting threshold; read those with
`read_phantom_statistics`; `PhantomBuilder.gather()` combines completed builder batches.

## Historical update: autumn 2021

The following notes by Saša Banjac document the library's development. Claims
about branches, removals, and planned tables describe that period. For current
file requirements and staging, use the references above.

* AtRIS now also simulates count rates using an advanced counting efficiency response matrix
   - The new phantom generation routines create this matrix
   - A separate branch of AtRIS has been created for the binary output required for the phantoms
   - Previous phantoms are removed. From now on, only ICRU sphere and a ramona phantom is available
   - 5 versions of the RAMONA DOSTEL phantom are created with various shielding thicknesses:
     0 mm Aluminium, 5 mm, 10 mm, 15 mm, 20 mm.
   - For the ICRU sphere, a similar set of shielded phantoms is being created.
   - Counting response matrices have the same phantom name, but the suffix "_counting" is expected
   - If a counting response matrix is not available, use ideal_counting_response.txt from the files directory
   - We now use only extended phantoms that consider also GCR nuclei

### Extended phantoms (historical notes)
These phantoms include response to GCR fully ionized nuclei from Z=3 to Z=28 (most abundant isotope).
For water, I've used .997 g per ccm as desnity, while for TEM it is 1.00 g per ccm

 * icru_b phantom is a r=15cm sphere of water
   -                shape: solid sphere
   -          composition: h2o
   -               radius: 15 cm
   -                 mass: 14094.7550 g
   -                 area: 1413.72 cm2
 * ramona phantom is a phantom corresponds to the RAMONA/DOSTEL detector A with aluminum shielding in front
   -                shape: disc
   -          composition: Si
   -               radius: 14.85 mm
   -            thickness: 0.315 mm
   -                 mass: 0.5082 g
   -                 area: 6.928 cm2
