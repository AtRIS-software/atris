# Editing documentation

The manual uses Sphinx, MyST Markdown, and the Read the Docs theme. Building it
requires Python 3.9 or newer. The `docs` extra installs the Python package and
its documentation tools; it does not build Geant4 or the AtRIS executable.
Read the Docs uses Python 3.12.

## Build locally

From the repository root, install the documentation extra:

```bash
python -m pip install -e ".[docs]"
```

Build the pages, treating warnings as errors:

```bash
python -m sphinx -a -b html -W --keep-going docs docs/_build/html
```

Serve the generated pages on your own computer:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory docs/_build/html
```

Open <http://localhost:8000>. Stop the server with Ctrl+C. After editing a page,
run the build command again from the repository root in another terminal, then
refresh the browser. `-a` rewrites every page so shared navigation changes
appear throughout the manual. After removing or moving pages, clean generated
output before rebuilding so obsolete HTML files are not left on the site:

```bash
python -m sphinx -M clean docs docs/_build
python -m sphinx -a -b html -W --keep-going docs docs/_build/html
```

On macOS, you can also open the built homepage directly:

```bash
open docs/_build/html/index.html
```

## Add a page

1. Choose the section according to the reader's purpose: Tutorials
   (`tutorials/`), Running AtRIS (`running-atris/`), Reference (`reference/`), or
   Background (`background/`).
2. Add a Markdown file with a single level-one title.
3. Add its filename, without `.md`, to a `toctree` block in that section's
   `index.md`. Paths in the block are relative to the index file.
4. Build locally and resolve warnings before submitting the change.

For example, a section containing `first-run.md` would include:

````markdown
```{toctree}
:maxdepth: 1

first-run
```
````

## Included source files

The installation page includes the root `INSTALL.md`; edit that file to change
installation instructions. The HPC page includes the example Slurm scripts;
edit the scripts themselves when changing their commands or defaults.

## Notebook tutorials

To open and edit the notebook locally, install the notebook extra and launch it:

```bash
python -m pip install -e ".[notebook]"
python -m jupyterlab docs/tutorials/exoplanet-psf.ipynb
```

Notebook pages use MyST-NB. The `docs` extra includes the kernel and plotting
libraries needed to execute them during a documentation build. Sphinx executes
self-contained notebooks in a temporary working directory and fails if a cell raises an error;
no Geant4 simulations or network downloads are part of the notebook build.
Use `python -m sphinx -E -b html -W --keep-going docs docs/_build/html` for a
fresh build that re-executes notebook sources.

Tutorial notebooks include saved tables and plots, visible both locally and in
the downloaded files. Self-contained examples execute again during a Sphinx or
Read the Docs build. The Earth spectrum-folding notebook instead displays its
saved outputs: regenerating them needs an existing Earth run and the published
spectrum table. Run it locally with your Earth results and save the notebook
to update those plots.

Run the exoplanet notebook in your simulation directory. It writes
`simulation.psf` there; rerunning the writing cell replaces that file.

## Read the Docs

The repository's `.readthedocs.yaml` installs the Python package with its `docs`
extra and builds this manual with warnings treated as errors. To publish,
connect the repository to Read the Docs and activate the desired branch or
release version.
Adding the configuration alone does not create or publish a hosted project.

See the [Read the Docs configuration guide](https://docs.readthedocs.com/platform/stable/config-file/).
