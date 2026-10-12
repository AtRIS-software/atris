# Phantom regeneration and retirement plan

Status: planned work, informed by initial transport tests. This plan does not
replace, rename, or remove the supplied tables.

Energy-fraction response files remain in `phantoms/`; deposited-energy
response files are in `MeV-valued/`. Regeneration remains planned.

Replace the collection of partly documented files with a small, reproducible
phantom library. Every supported phantom should have a generation recipe,
physical specification, explicit response quantities, and validation results.
Users should be able to choose between tissue-equivalent material and water.

## Phantoms to regenerate

| Phantom | Physical specification | Evidence and remaining work |
| --- | --- | --- |
| ICRU tissue-equivalent sphere | Radius 15 cm; density 1 g/cm³; mass fractions O 76.2%, C 11.1%, H 10.1%, N 2.6% | Generate separately from water and compare their responses. No tissue-equivalent reconstruction has been run in this investigation yet. |
| Water sphere | Radius 15 cm; liquid water, density 0.997 g/cm³ | Initial proton tests agree with the older supplied ICRU-labelled table within 1.4% at the three tested energies. The newer table remains unexplained. |
| Cell | Water sphere, radius 50 μm | Published geometry; initial proton tests agree with the supplied `cell` response within 2.6%. |
| Bacterium | Candidate water sphere, radius 4 μm | Inferred from size tests; proton responses agree within 3.4%. Establish a documented definition rather than treating this as recovered historical provenance. |
| Small bug | Candidate water sphere, radius 1 mm | Proton responses agree within 2.6%. As for the bacterium, the original geometry specification has not been recovered. |

Use distinct names for the tissue-equivalent and water spheres. Do not retain
`icru` as an ambiguous name for either material. The biological models represent
energy deposition in simple volumes, not anatomical organisms or biological
damage mechanisms.

Keep unshielded **RAMONA detector A** as a secondary regeneration target and a
useful nonspherical validation case: silicon, radius 14.85 mm, thickness 315 μm.
The initial cosine-incidence proton tests agree with its supplied response
within 2.3%. The complete instrument, shielding, other species, and historical
variants have not been reconstructed.

The geometry sources are [Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622),
[Herbst et al. (2020), section 4.3](https://doi.org/10.1051/0004-6361/201936968),
and the [historical library notes](../docs/reference/phantom-library.md#extended-phantoms-historical-notes).
The [local pilot report](../../runs/phantom-reconstruction-tests/findings.txt)
records the 34 runs, 52,000 protons, settings, uncertainties, and limitations.
These spot checks support recipes; they are not validation of complete tables.

## Resolve normalization before publishing replacements

The current sphere “area” combines geometry with a conversion between interface
crossings and phantom interceptions. This is a design concern, not yet proof
that the numerical factor is wrong in its intended setting.

For an isotropic intensity $J$, measured per unit area perpendicular to the
particle direction, per unit time and solid angle, the crossing rate through
both sides of a plane per unit plane area is

$$
C=2\pi J.
$$

A sphere of radius $r$ intercepts particles at rate

$$
R=4\pi J\,\pi r^2,
\qquad \frac{R}{C}=2\pi r^2.
$$

This explains a possible origin of the current factor. It does not make
$2\pi r^2$ an intrinsic geometric area. For a parallel beam normal to the
scoring plane, the corresponding ratio is instead $\pi r^2$. A single constant
cannot cover arbitrary angular distributions. The calibration's angular
averaging and the atmospheric crossing estimator must be considered together.

The audit should:

1. Trace a response from calibration events through table writing, C++ scoring,
   gathering, post-processing and physical-spectrum folding. Record units,
   denominators, energy factors, mass factors and angular assumptions at each
   step. Check the configurable response channels in `run-configuration` as
   well as `main`; do not assume the historical scorer is the only interface.
2. Compare direct phantom irradiation with the interface-crossing/table method
   in the same known field: isotropic, perpendicular beam, oblique beam, and
   mixtures with different upward/downward intensities and energy spectra.
   Use a sphere and a disk, specifying the disk orientation and exposed faces.
3. Check invariance under changes to the artificial scoring surface, with the
   incident physical field held fixed. Separate crossing counts, scalar fluence,
   and intercepted-particle counts rather than calling all of them “flux.”
4. Decide whether an explicitly limited isotropic estimator is sufficient or
   whether angular information or a different fluence estimator is needed.
   Do not silently replace $2\pi r^2$ with $\pi r^2$, or introduce an angular
   correction without validating the resulting estimator.

Store geometric dimensions and derived mass separately from source and scoring
normalization. For a homogeneous sphere, $m=\rho\,4\pi r^3/3$. Any effective
area must identify its convention and assumptions. Users should select these
properties together with the matching table, not independently resize a phantom
by editing mass or area.

## Make generation reproducible

Build on the calibration helpers, with shared event accumulation and table I/O.
Add material and geometry support where needed; avoid a separate generator for
each phantom. Keep readable worked examples for a sphere and a disk.

Each generated phantom should include:

- Geometry, elemental composition, density, dimensions, mass, shielding and
  orientation, with the source of the specification.
- Source positions and directions, incident-energy sampling and bin edges,
  particle identifiers, and ion energy/charge conventions.
- Geant4 version, physics list, production cuts, tracking settings, seeds,
  event counts, and the exact generation code and inputs.
- Explicit quantity and units for every response. Distinguish total energy
  deposition, ionizing deposition, energy fraction and counting efficiency.
  Specify whether thresholds gate only counting or also energy responses.
- Event variance and uncertainty of the estimated mean, clearly distinguished;
  sampling counts and unsampled bins must remain identifiable.
- Calibration and application normalization, plus comparisons and their
  statistical uncertainties. Preserve a small rerunnable validation dataset.

Sum deposits from all secondary tracks belonging to each incident primary;
include zero-deposit events in the denominator. For biological phantoms, do not
present a unit counting table as a calculated detection efficiency. Generate
counting responses only for a defined observable and threshold.

First extend the small tests to electrons, photons, neutrons and representative
ions. Check cut sensitivity, particularly for micrometre geometries, and test
thresholds and bin sampling. Then populate the supported species and energy
grid with sufficient statistics. Missing results must not become measured zeros.

## Retire the remaining library

After validated replacements exist, make the regenerated core set the supported
library. Remove historical `_old`/unsuffixed duplicates, unexplained RAMONA
variants (`flatramona`, `randramona`, `realramona`), and unmaintained shielding
series from the active selection. Regenerate a shielded variant only when there
is a concrete use and a defined geometry; it need not remain a default offering.

Preserve the original files byte-for-byte in a clearly separate legacy archive,
with checksums, notes, original filenames and a mapping to replacements where
one exists. Keep existing runs reproducible. Do not silently redirect an old
stem to a new material or calibration. Retired does not mean deleted or proven
incorrect; it means no longer maintained as a supported calibration.

Update staging, examples and documentation to select the new identities. Check
their mass and normalization metadata together with the selected tables. Keep
the unexplained newer-ICRU discrepancy documented until its cause is established;
regenerating a replacement does not explain the historical difference.

## Completion criteria

The work is complete when each supported phantom can be regenerated from its
saved specification, its intended scoring and normalization agree with direct
transport within stated numerical/statistical tolerances, and the examples use
those validated products. The supported angular assumptions and unresolved
physical limitations should be explicit. Archive the superseded library only
after the replacements and migration have been checked.
