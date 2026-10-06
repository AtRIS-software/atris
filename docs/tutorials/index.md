# Tutorials

Follow the Earth example from an atmosphere model to ionization and dose
rates, or build your own atmosphere with the exoplanet notebook.

```{toctree}
:hidden:

earth-nrlmsis-full
run-earth-simulation
earth-spectrum-folding
exoplanet-psf
```

## Earth simulation

1. [Prepare an Earth atmosphere simulation](earth-nrlmsis-full.md): turn the
   supplied atmosphere model into simulation inputs, including optional
   detector and dose calculations.
2. [Run and inspect the Earth simulation](run-earth-simulation.md): run the
   first part of the calculation, combine its results, and inspect the plots.
3. [Apply a cosmic-ray spectrum](earth-spectrum-folding.ipynb): use the
   simulated proton responses to calculate ionization and dose rates.

The third tutorial is a Jupyter notebook at
`docs/tutorials/earth-spectrum-folding.ipynb`.
[View notebook](earth-spectrum-folding.ipynb) or download
{download}`earth-spectrum-folding.ipynb <earth-spectrum-folding.ipynb>`.

## Create your own atmosphere

[Make a PSF for a simple exoplanet](exoplanet-psf.ipynb) builds a mixed-gas
atmosphere with NumPy, plots its profiles, and writes `simulation.psf`.
This Jupyter notebook is at `docs/tutorials/exoplanet-psf.ipynb`.
[View notebook](exoplanet-psf.ipynb) or download
{download}`exoplanet-psf.ipynb <exoplanet-psf.ipynb>`.
