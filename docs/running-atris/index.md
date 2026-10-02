# Running AtRIS

Prepare the physical model, run a few chunks, and inspect their results before
continuing the full calculation. The preparation and result processing are the
same locally, on a server, and on an HPC system. The first chunks remain part
of the run if you decide to continue.

```{toctree}
:hidden:

installation
use-atris-on-uio
prepare-simulation
plan-chunks
run-simulation
process-results
```

## Installation and session setup

[Install AtRIS](installation.md) before preparing a run. On UiO Geosciences
servers, use the [UiO installation and session guide](use-atris-on-uio.md) for
shared Geant4 paths, modules, and resource policies.

For an installation using the supplied setup script, load it in each new shell
from the AtRIS directory:

```bash
source setup_atris.sh
```

Then change to the directory where you keep your runs. The setup locates AtRIS
and Geant4; it does not select a planetary model or create simulation inputs.

## Prepare, run, and inspect

1. [Prepare the simulation](prepare-simulation.md): supply `simulation.psf`,
   convert the geometry, stage any phantoms, prepare particle inputs, and record
   the physics.
2. [Plan chunks and restarts](plan-chunks.md): divide the requested events and
   choose a practical balance between startup overhead and recovery time.
3. [Run a few chunks](run-simulation.md): execute selected plan entries locally,
   on a server, or through an HPC scheduler.
4. [Gather and inspect](process-results.md): normalize the completed responses,
   plot the inputs and results, and assess runtime.
5. [Decide whether to continue](process-results.md#decide-whether-to-continue):
   launch the remaining plan if the setup looks right, or revise it based on
   the first results. Keep inspecting as more chunks finish.

To learn by following a complete example, use the [tutorials](../tutorials/index.md).
