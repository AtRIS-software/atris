# AtRIS: Atmospheric Radiation Interaction Simulator

AtRIS (Atmospheric Radiation Interaction Simulator) is a research code for
studying radiation in planetary atmospheres and surfaces. It was originally
described by [Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042).
AtRIS follows energetic particles as they pass through an atmosphere and into
the ground, tracking the secondary particles they produce and the energy they
leave behind. It uses [Geant4](https://geant4.web.cern.ch/), a toolkit for
simulating particle interactions with matter. These calculations show how the
atmosphere and surface shape the radiation reaching different altitudes and
depths.

Researchers have used AtRIS to study how cosmic rays affect atmospheric
chemistry and potential signs of life in the spectra of modern Earth
([Herbst et al., 2019](https://doi.org/10.1051/0004-6361/201935888)) and
TRAPPIST-1e ([Herbst et al., 2024](https://doi.org/10.3847/1538-4357/ad0895)).
It has also been used to compare summer and winter muon fluxes on Earth
([Al-Qaaod et al., 2025](https://doi.org/10.1029/2025JA034303)) and to
investigate how Martian soil shields the subsurface from radiation
([Röstel et al., 2020](https://doi.org/10.1029/2019JE006246)). Dose calculations
are another application: the phantom method of
[Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622) estimates the
energy deposited in a material or detector. Its uses extend from human
radiation exposure to microbial cells in Venus's clouds
([Herbst et al., 2020](https://doi.org/10.1051/0004-6361/201936968)). The original
AtRIS paper has been cited by
[over 40 peer-reviewed publications](https://ui.adsabs.harvard.edu/search/q=citations%282019JGRA..124...50B%29%20property%3Arefereed);
[Research applications](background/research-applications.md) gives a fuller
account of these studies.

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
