# Writing and previewing documentation

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

Use relative Markdown links for other manual pages. Keep command examples
explicit about their working directory. Mark unwritten material as planned
rather than presenting it as a completed guide.

## Keep each subject in one place

Tutorials retain runnable examples and their intermediate files. Running AtRIS
contains reusable procedures for the reader's own simulation. Background explains
the physical model and interpretation; Reference defines formats, options, and
implementation-specific behavior. Keep a brief reminder where it helps the
reader, but link to the full procedure or definition instead of copying it.

The installation page includes the root `INSTALL.md`; edit that file to change
installation instructions. The HPC page includes the example Slurm scripts;
edit the scripts themselves when changing their commands or defaults.

After structural edits, check the actual served pages as well as the build:
section titles, sidebar links, section anchors, and notebook view/download links
must work. Update all references to a moved page, including notebook Markdown.

## Notebook tutorials

To open and edit the notebook locally, install the notebook extra and launch it:

```bash
python -m pip install -e ".[notebook]"
python -m jupyterlab docs/tutorials/exoplanet-psf.ipynb
```

Notebook pages use MyST-NB. The `docs` extra includes the kernel and plotting
libraries needed to execute them during a documentation build. Sphinx executes
notebooks in a temporary working directory and fails if a cell raises an error;
no Geant4 simulations or network downloads are part of the notebook build.
Use `python -m sphinx -E -b html -W --keep-going docs docs/_build/html` for a
fresh build that re-executes notebook sources.

Keep notebook code independent of the working directory and declare its Python
dependencies in `pyproject.toml`. Save source notebooks with outputs cleared to
avoid committing generated plots and local paths; the website builds its own
outputs. Local execution of the exoplanet notebook writes its model files in
`exoplanet-inputs/` beneath the kernel's working directory. Read the cells before
changing that output destination or rerunning exports.

## Maintaining the reference

Check reference changes against the implementation in the same revision.
Command pages include captured `--help` output; refresh that block when a
command's parser changes, and update its input/output and overwrite descriptions.
For output formats, check both the C++ writer and Python reader/post-processor,
including units and normalization.

## Read the Docs

The repository's `.readthedocs.yaml` installs the Python package with its `docs`
extra and builds this manual with warnings treated as errors. To publish,
connect the repository to Read the Docs and activate the desired branch or
release version.
Adding the configuration alone does not create or publish a hosted project.

See the [Read the Docs configuration guide](https://docs.readthedocs.com/platform/stable/config-file/).

## Mathematical notation

Use LaTeX mathematics: `$...$` for inline expressions and `$$...$$` on separate
lines for display equations. MyST and MathJax render these in the manual; the
same notation works in notebook Markdown cells. Define symbols and connect
them to code variable names where useful. Keep executable Python, shell
commands, and literal file contents in code blocks.

## AtRIS command names

Use the `atris-` commands in tutorials and running instructions, including
installation checks. Keep legacy aliases, direct executable invocations, and
Python-module command alternatives in Reference.

## Workflow navigation

Label links “Previous step” or “Next step” only for actions that actually
precede or follow the page's task. A starting tutorial has no previous step,
and a completed workflow has no next step. Alternative examples, reference
pages, overviews, and background explanations are ordinary descriptive links,
not workflow steps. Keep valid step links at the opening and end of the page.
The theme's automatic page-order navigation is disabled for this reason.

When introducing a notebook, give its project-relative location and provide
both a normal page link labelled “View notebook” and a `{download}` link labelled
with the `.ipynb` filename. Render archived notebooks with execution disabled
in their `mystnb.execution_mode` metadata so their saved outputs can be read
without rerunning historical analyses.

For run-directory examples, create the run directory with `mkdir`, enter it
with `cd`, then copy inputs and run preparation commands from inside it.
Keep existing example directory names and filenames when copying them.

Assume run examples start inside `runs/` in the recommended sibling layout,
but write commands relative to the current working directory. Do not derive
simulation destinations from `ATRIS_ROOT`; it identifies the installation,
not the storage location for results.
The recommended layout keeps `runs/` beside AtRIS. State that recommendation
without making it a requirement or hard-coding it into run commands.
