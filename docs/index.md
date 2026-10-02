# AtRIS documentation

AtRIS (Atmospheric Radiation Interaction Simulator) is a particle-transport
code for studying radiation in planetary and exoplanetary atmospheres.
AtRIS was originally developed by Saša Banjac; see
[Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042).

The atmosphere and regolith models in AtRIS allow researchers to
investigate how a planet's composition and structure affect the radiation
reaching different altitudes and the surface. By following incoming particles
and the secondary particles they produce, AtRIS supports studies of
atmospheric ionization, chemistry, and habitability.

The transport calculation uses [Geant4](https://geant4.web.cern.ch/), a toolkit for simulating the passage of
particles through matter. Geant4 provides the models of physical interactions;
AtRIS defines the planetary environment and incident radiation and records
the simulation results. For dose and detector-response calculations, AtRIS weights particle
crossings with precomputed phantom response tables.

## Working with AtRIS

This manual follows a simulation from its physical setup to its results.
Preparation and post-processing are shared across local, server/workstation,
and HPC runs; the execution guides cover the job setup for each environment.

1. [Prepare the simulation](running-atris/prepare-simulation.md): define the planet,
   select any phantoms, and prepare the particle sampling and physics choices.
2. [Plan and run a few chunks](running-atris/run-simulation.md): create a chunk
   plan and execute a small part of it on your computer, a server, or an HPC system.
3. [Gather and inspect](running-atris/process-results.md): process the completed
   chunks and check the input plots, initial responses, and runtime.
4. [Decide whether to continue](running-atris/process-results.md#decide-whether-to-continue):
   keep running if the setup looks right, or revise it based on the first results.
   Completed chunks remain part of a continued run with the same setup.

The [tutorials](tutorials/index.md) provide worked examples of model preparation
and a complete simulation workflow. The [reference](reference/index.md)
describes commands, input formats, and output quantities.

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
