# AtRIS documentation

AtRIS (Atmospheric Radiation Interaction Simulator) is a particle-transport
code for studying radiation in planetary and exoplanetary atmospheres.
AtRIS was first described in
[Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042).

The original AtRIS paper has been cited by
[over 40 peer-reviewed publications](https://ui.adsabs.harvard.edu/search/q=citations%282019JGRA..124...50B%29%20property%3Arefereed).
AtRIS has been used to study
[atmospheric ionization on Earth](https://doi.org/10.3390/universe9120502),
[radiation exposure and subsurface shielding on Mars](https://doi.org/10.1029/2019JE006246),
[radiation doses in Venus's clouds](https://doi.org/10.1051/0004-6361/201936968),
and [cosmic-ray effects on atmospheric chemistry and exoplanet biosignatures](https://doi.org/10.1051/0004-6361/201935888).

The transport calculation uses [Geant4](https://geant4.web.cern.ch/), a toolkit for simulating the passage of
particles through matter. Geant4 provides the models of physical interactions;
AtRIS defines the planetary environment and incident radiation and records
the simulation results. For dose and detector-response calculations, AtRIS weights particle
crossings with precomputed phantom response tables.

## Working with AtRIS

An AtRIS calculation starts with a model of the planet's atmosphere and
surface. You then prepare and run particle simulations to find out how
radiation interacts with that environment.

1. [Prepare the simulation](running-atris/prepare-simulation.md): build the
   planet model and set up the particle types and energies to simulate.
2. [Start running](running-atris/run-simulation.md): run part of the calculation
   on your computer, a server, or a computing cluster.
3. [Inspect the results](running-atris/process-results.md): examine the plots
   and assess how much computing time the full calculation will need.
4. [Continue as needed](running-atris/process-results.md#decide-whether-to-continue):
   build on the completed work until you have enough simulated particles to
   answer your question reliably.

The [tutorials](tutorials/index.md) walk through this process using worked
examples. The [reference](reference/index.md) explains the commands, file
formats, and calculated quantities.

For installation, see [Installing AtRIS](running-atris/installation.md) or the
[UiO setup guide](running-atris/use-atris-on-uio.md).

```{toctree}
:maxdepth: 2
:caption: User documentation

background/index
tutorials/index
running-atris/index
reference/index
```

```{toctree}
:maxdepth: 1
:caption: Project documentation

development
reference/minimal-test-fixture
known-bugs
contributing-docs
```
