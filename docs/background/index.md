# Background

Radiation at a planet's surface is shaped by what happens above it. An incoming
particle can lose energy, change direction, or produce secondary particles as
it travels through the atmosphere. Those secondaries can themselves interact,
so the radiation reaching a given altitude differs from the radiation entering
at the top. AtRIS follows these particle histories to estimate energy deposition
and the response of selected detectors or materials throughout a planetary model.

```{toctree}
:hidden:

geant4-and-atris
software-ecosystem
planetary-geometry
physics-lists
radiation-quantities
normalization-and-uncertainty
```

## From a planetary model to particle histories

The physical setup combines a material model, an incident particle source, and
a choice of interaction models. The material model is supplied in
`simulation.psf`: it describes the atmosphere and surface as layers with specified
composition and physical properties. Density and layer thickness determine how
much material a particle encounters; composition affects how it interacts.
[Planetary geometry](planetary-geometry.md) explains these relationships.

[Geant4](https://geant4.web.cern.ch/) supplies the particle transport and
interaction models. AtRIS defines the planetary environment and records what
happens within it. The selected physics list determines which processes and
models Geant4 uses. The pages on [Geant4 and AtRIS](geant4-and-atris.md) and
[physics lists](physics-lists.md) explain their respective roles. For geometry
inspection, data analysis, and scientific file formats, see the
[software ecosystem](software-ecosystem.md): Geant4, pyg4ometry, ROOT, and HDF5.

The calculation uses Monte Carlo sampling. For example, one incoming proton
may generate many secondary particles, each contributing energy deposition or
crossing a layer boundary. Together, these belong to one primary history.
Repeating the calculation for many primaries builds a statistical estimate of
the atmospheric response. [Follow one incoming proton](geant4-and-atris.md#follow-one-incoming-proton)
shows what is followed and recorded.

## What the results represent

Energy deposited in an atmospheric layer and dose in a detector are different
quantities. AtRIS records atmospheric ionizing energy deposition directly.
Optional phantom tables describe how a particular detector or material responds
to the particles crossing a layer boundary. They allow that response to be
estimated without placing a physical detector at every altitude.
[Radiation quantities](radiation-quantities.md) explains ionization, absorbed
dose, radiation weighting, and counting responses.

After normalization, the response tables describe the result per simulated
primary, resolved by primary energy. A physical rate additionally requires an
incident particle spectrum and its intensity. More simulated histories improve
the statistical estimate; they do not represent a stronger physical source.
[Normalization and uncertainty](normalization-and-uncertainty.md) explains this
distinction and how to assess the sampling uncertainty.

The original AtRIS model is described in
[Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042).
For the commands that prepare, execute, and process a simulation, see
[Running AtRIS](../running-atris/index.md).
