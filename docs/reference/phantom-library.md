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
It constructs the water sphere in GDML, irradiates it with protons in Geant4,
and compares its energy response with the older and later supplied tables.

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

Pass `**particle_source(pdg)` to `prepare_water_phantom` in
`atris_tools.phantom_calibration`. Named particles include antiparticles and
the light nuclei `deuteron`, `triton`, `He3`, and `alpha`. Other positive
ground-state nuclei use an ion source; they are fully stripped unless
`particle_source` receives an explicit `charge`. The charge state does not
change the PDG code. Excited states, hypernuclei, and generic antinuclear
sources are outside this helper's scope.

`prepare_water_phantom` writes the geometry and chunk inputs;
`read_water_phantom_events` reads completed chunks into NumPy arrays;
`calibrate_water_phantom` calculates the fixed-grid responses and sampling
errors. Its `PhantomResponse.write` method writes the response and counting
tables, `phantoms.txt`, and sampling metadata. By default it rejects unsampled
energy bins. The [notebook](../tutorials/water-phantom.ipynb)
shows both source setups and the complete export workflow.

Generated tables contain `#` headers describing the geometry, material, energy
grid, units, normalization, counting criterion, sampling uncertainties and
generation settings; see [response-table headers](inputs.md#phantom-response-matrices).
The C++ reader skips all comments and reads coefficients unchanged.

`compact_water_phantom_chunk(path)` retains the per-primary energy sums,
histograms and metadata needed for calibration, while removing detailed
transport-step and interface-crossing records. It verifies the event arrays
before replacing the generated chunk file and records the discarded ntuples
in that file. `read_water_phantom_events` reads either representation.
The notebook uses `shower` output to retain individual events and explore
counting thresholds. The internal `phantom` output mode instead stores per-bin
statistics with a zero counting threshold; read those with
`read_phantom_statistics` or combine them with `calibrate_water_phantom`.

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

## Archived exploration notebook

[View notebook](notebooks/explorer_v2.ipynb) to read the original phantom
exploration code and saved outputs, or download
{download}`explorer_v2.ipynb <notebooks/explorer_v2.ipynb>` to work locally.
The Jupyter notebook is located at `docs/reference/notebooks/explorer_v2.ipynb`
in the project. This is an archived
development notebook, not an automatically executed tutorial.

It uses NumPy, Matplotlib, and pandas, reads response, variance, and counting
tables from the kernel's working directory, and expects `../phantom.bins`.
That bin file is not provided at that path in this checkout. Before running,
configure the working directory and supply or update the bin-file path. The
code also writes PDF plots to its working directory. The original notebook is
preserved without changing its analysis.

```{toctree}
:hidden:

notebooks/explorer_v2
```
