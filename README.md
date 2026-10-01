# AtRIS

AtRIS (Atmospheric Radiation Interaction Simulator) is a particle-transport
code for studying radiation in planetary and exoplanetary atmospheres.
AtRIS was originally developed by Saša Banjac; see
[Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042).

By following incoming particles and the secondary particles they produce,
AtRIS shows how atmospheric and regolith composition affect radiation at
different altitudes and at the surface. These calculations support studies
of atmospheric ionization, chemistry, and habitability.

The transport calculation uses [Geant4](https://geant4.web.cern.ch/), a toolkit
for simulating the passage of particles through matter. AtRIS supplies the
planetary model and incident radiation, records energy deposition and particle
crossings, and uses optional phantom response tables for dose and detector
response calculations.

This repository includes the simulator, Python tools for preparing and
analyzing simulations, phantom response tables, and worked examples.

**[Documentation](docs/index.md)** · **[Installation](INSTALL.md)** ·
**[Tutorials](docs/tutorials/index.md)**

## Getting started

Follow the [installation guide](INSTALL.md) to build AtRIS and install the
Python tools. To try the complete workflow,
[run a few chunks of the Earth example](docs/tutorials/files-through-workflow.md)
and inspect their results before continuing the run.

For a scientific model, begin with
[Prepare an Earth atmosphere simulation](docs/tutorials/earth-nrlmsis-full.md),
or use the [exoplanet notebook](docs/tutorials/exoplanet-psf.ipynb) to create a
planet specification file from scratch. The
[workflow tutorial](docs/tutorials/files-through-workflow.md) follows the input
and output files from preparation through analysis.

Simulations run in independent, restartable chunks on a local computer, a
server, or an HPC system. Start with a few chunks, gather and inspect their
plots, then decide whether to continue the remaining plan or revise the setup.
Completed chunks are retained when you continue. See
[Running AtRIS](docs/running-atris/index.md) for planning, execution, and result
processing.

## Documentation

The [manual](docs/index.md) contains tutorials, running instructions,
[command and file references](docs/reference/index.md), and
[background on the physics and software](docs/background/index.md).
Follow the [local preview instructions](docs/contributing-docs.md#build-locally)
to build and browse the complete documentation.

For work on the code, see the [development guide](docs/development.md) and
[known issues](docs/known-bugs.md).

## License

AtRIS is distributed under the [GNU General Public License, version 2 or
later](LICENSE).
