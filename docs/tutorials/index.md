# Tutorials

The preparation tutorials below offer two ways to build simulation inputs.
They are alternatives, not consecutive steps. The complete workflow tutorial
then follows prepared inputs through execution and results processing.

```{toctree}
:hidden:

earth-nrlmsis-full
exoplanet-psf
files-through-workflow
```

## Prepare model inputs

[Prepare an Earth atmosphere simulation](earth-nrlmsis-full.md) uses supplied
Earth atmosphere data and prepares the geometry, optional phantom responses,
and particle inputs. The workflow tutorial below runs a few chunks of this model.

[Create an exoplanet PSF](exoplanet-psf.ipynb) builds a simple atmosphere with
NumPy, plots its profiles, and writes the primary model input. This is a Jupyter
notebook at `docs/tutorials/exoplanet-psf.ipynb` in the project.
[View notebook](exoplanet-psf.ipynb) or download
{download}`exoplanet-psf.ipynb <exoplanet-psf.ipynb>` to run it locally.

## Follow the complete workflow

[Follow the files through an AtRIS run](files-through-workflow.md) starts from
a supplied PSF and covers preparation, execution, and results, showing which
files each step reads and writes. It runs one proton chunk and one alpha chunk
before gathering results. Inspect the plots and decide whether to continue the
remaining plan or revise the setup. You can start
here directly if you already have a model or want an overview of the whole run.

The reusable guides follow the same sequence:
[prepare the simulation](../running-atris/prepare-simulation.md),
[plan chunks](../running-atris/plan-chunks.md), [run it](../running-atris/run-simulation.md), and
[process the results](../running-atris/process-results.md).
