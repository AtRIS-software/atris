# Ionization, dose, and detector response

AtRIS records energy deposition and phantom responses. Post-processed tables
are normalized per simulated primary and resolved by primary energy. To obtain
physical rates, [apply an incident spectrum and intensity](normalization-and-uncertainty.md#apply-a-physical-source-separately).
The sections below explain what each quantity measures; the
[output reference](../reference/outputs.md#processed-response-tables) gives exact
units and normalization formulas.

## Ionizing energy deposition

The ionization tally accumulates total deposited energy minus non-ionizing
deposition in each sensitive layer. After post-processing, `.ioni` contains
ionizing energy deposition per unit volume per simulated primary, resolved by
primary-energy bin. Its units are MeV cm$^{-3}$ primary$^{-1}$.

This is not yet the number of ion pairs produced. Given an appropriate mean
energy $W$ required to form one ion pair, an estimate is

$$
N_{\mathrm{pairs}}=\frac{E_{\mathrm{ion}}}{W}.
$$

Use consistent energy units. The choice of $W$ depends on the material;
AtRIS does not supply a universal value.

## Total atmospheric energy deposition

The total-deposition tally accumulates Geant4's total local energy deposit for
the same steps as the ionization tally. After post-processing, `.edep` contains
total deposited energy per unit volume per simulated primary, resolved by
primary-energy bin, in MeV cm$^{-3}$ primary$^{-1}$.

The difference `.edep - .ioni` is the correspondingly normalized non-ionizing
energy deposition. Converting `.edep` into atmospheric heating also requires
an assumption about thermalization efficiency.

## Phantom responses

A phantom represents a detector or material with a particular geometry and
shielding. AtRIS uses precomputed response tables for particles crossing layer
interfaces; selecting a table does not insert a physical detector into the
planetary geometry or alter the surrounding particle transport. Choose a table
that represents the material and detector response you want to study. The
[phantom library](../reference/phantom-library.md) describes the supplied examples.
The calculation of energy-response tables and their use for absorbed and
radiation-weighted dose are described by
[Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622), which extends the
original AtRIS description with the phantom method and a balloon-data comparison.
The [runtime discussion](what-determines-runtime.md#phantom-responses)
explains the additional scoring, memory, and output costs of selecting phantoms.

## Absorbed dose

Absorbed dose is energy deposited per unit mass:

$$
D=\frac{E_{\mathrm{dep}}}{m},\qquad 1\ \mathrm{Gy}=1\ \mathrm{J\,kg^{-1}}.
$$

AtRIS's phantom dose response is calculated from particles crossing an
interface and the selected phantom's response table. It is distinct from the
energy deposited directly in an atmospheric shell. The post-processor applies
primary-count, phantom-mass, and area normalization, but does not convert the
result to gray or apply a physical source flux. With the expected energy-fraction
tables, the processed response is in eV g$^{-1}$ per primary.

## Radiation-weighted response

Equal absorbed doses from different radiation types can have different
biological effects. Radiation protection accounts for this using dimensionless
weights $w_R$. The corresponding [equivalent dose](https://icrpaedia.org/Equivalent_dose)
is $H=\sum_R w_R D_R$, where $D_R$ is the absorbed dose from radiation type $R$.

The `.equiN` files contain AtRIS's radiation-weighted phantom response. At each
interface crossing, AtRIS looks up the phantom's energy response for the
crossing particle's species and kinetic energy. It multiplies that contribution
by a radiation weight before adding it to the histogram. The weights are
implemented in AtRIS, separately from the phantom tables and Geant4 transport.

For example, `protons.equi1` describes showers initiated by protons, scored
for phantom 1 (the water sphere in the Earth example). Secondary neutrons,
photons, and other supported particles contribute with their own weights;
the result is therefore not simply `protons.dose1` multiplied by the proton
weight. Rows give altitude and columns give incoming primary energy, as in
the [other processed response tables](../reference/outputs.md#processed-response-tables).

Gathering sums the raw histograms. Post-processing applies the same primary-count,
mass, and area normalization as for `.doseN`.
`.equiN` is in radiation-weighted eV g$^{-1}$ per primary; a physical dose rate
still requires unit conversion and an incident spectrum. It is not effective
dose, which also requires tissue weighting and an anatomical model.

The current weights differ from ICRP Publication 103 in the neutron formula and
pion selection. See the [possible radiation-weighting bug](../known-bugs.md#possible-radiation-weighting-bug)
for these discrepancies and the [output reference](../reference/outputs.md#radiation-weighting-as-implemented)
for the exact implemented formula.

## Counts and count rates

The counting table supplies the detector response for a crossing particle,
recorded in `.ratesN` after post-processing. Different detector tables can
produce different counting responses to the same transported particle field.

```{figure} ../images/earth-example/protons.icru_zero_0.000MeV_detAB_old.png
:name: earth-phantom-responses
:alt: Three energy-altitude response matrices for the ICRU water sphere: absorbed dose, radiation-weighted dose, and counting response to proton-initiated showers.
:width: 100%

The ICRU water sphere's responses to proton-initiated showers in the Earth example:
absorbed dose, radiation-weighted dose, and counting response. These are
responses per simulated primary; physical rates
require an incident spectrum and intensity.
```

[Open the full-size phantom responses](../images/earth-example/protons.icru_zero_0.000MeV_detAB_old.png).

## Implementation

`src/SensitiveDetector.cc` implements the tallies and radiation weights;
`atris_tools/postprocess.py` implements the output normalization.
