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
Python tools. Then [prepare the Earth example](docs/tutorials/earth-nrlmsis-full.md)
and [run and inspect a few chunks](docs/tutorials/run-earth-simulation.md).
The tutorials explain the input and output files at each step.

To create your own atmosphere, use the [exoplanet notebook](docs/tutorials/exoplanet-psf.ipynb).
For running your model locally, on a server, or on an HPC system, see
[Running AtRIS](docs/running-atris/index.md).

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
