# Download an atmosphere from NASA and prepare it for AtRIS

**Next step:** [Select phantoms and prepare particle inputs](prepare-simulation.md#optionally-select-phantoms).

NASA's [NRLMSIS form](https://ccmc.gsfc.nasa.gov/instantrun/nrlmsis/)
provides Earth atmosphere profiles that AtRIS can convert into a PSF.

## Download the atmosphere

Create and enter a run directory, starting from `runs/`:

```bash
mkdir earth-atmosphere
cd earth-atmosphere
```

In the NASA form, select **NRLMSIS 2.0**, enter the date, UTC time, and location,
and choose **Height** as the profile type. For a 100 km atmosphere with 1 km
layers, use **Start: 0**, **Stop: 99**, and **Step Size: 1**. Each sampled altitude
becomes the bottom of a layer, so the final layer extends from 99 to 100 km.

Leave the optional solar and geomagnetic activity fields at `-1` to use NASA's
datasets. Recent dates may require you to supply those values yourself.

Click **Submit** and save the text from **Download Output** or **View Raw Output**
as `nrlmsis_output.txt` in the run directory.

## Convert it for AtRIS

From that directory, run:

```bash
atris-nrlmsis-to-psf nrlmsis_output.txt --output simulation.psf
atris-psf-to-gdml simulation.psf
```

The first command creates `simulation.psf` from the atmosphere table. The
second creates `simulation.gdml`, the geometry used by Geant4. The atmosphere
profile is represented as spherical layers around Earth.

Continue with [phantom selection](prepare-simulation.md#optionally-select-phantoms),
then generate the particle macros and energy bins. Phantoms are optional.

The [Earth example](../tutorials/earth-nrlmsis-full.md) also includes downloaded
atmosphere tables, ready to use.

**Next step:** [Select phantoms and prepare particle inputs](prepare-simulation.md#optionally-select-phantoms).
