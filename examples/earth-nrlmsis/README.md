# Reduced Earth atmosphere example

This directory contains prepared inputs for a short end-to-end AtRIS run. The
atmosphere is an NRLMSIS 2.0 profile for 18 August 2026 at 00:00 UTC, 55 degrees
north and 45 degrees east. It covers 0 to 1000 km in 50 km steps.

The particle inputs use ten logarithmically spaced energy points. The proton
macro runs 20 events from 1 to 1000 MeV, while the alpha macro runs 10 events
from 4 to 4000 MeV. Both macros request four Geant4 worker threads. These small
event counts are suitable for checking the installation and workflow, not for
scientific results.

The source atmosphere table is retained as `nrlmsis_output.txt`.
`simulation.psf` is the converted Planet Specification Format file, and
`simulation.gdml` is the resulting Geant4 geometry. The proton and alpha GDML,
macro, and energy-bin files are ready to run. `phantoms.txt` selects two of the
response tables supplied in the repository.

## Run the example

From `<ATRIS_WORK>`, prepare a run directory without modifying the committed
example:

```bash
source atris/setup_atris.sh
atris-clone atris/examples/earth-nrlmsis runs/earth-nrlmsis
cd runs/earth-nrlmsis
atris-stage-phantoms .
```

Run the two particle species:

```bash
AtRIS FTFP_BERT_HP protons -1 2
AtRIS FTFP_BERT_HP alphas -1 2
```

Post-process and plot the results:

```bash
postprocess
atris-plot
```

The example intentionally excludes simulation outputs, plots, logs, and copies
of the phantom response tables.
