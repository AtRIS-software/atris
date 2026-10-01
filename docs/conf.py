"""Build the AtRIS manual without building the AtRIS executable or Geant4."""

project = "AtRIS"
extensions = ["myst_nb", "sphinxcontrib.mermaid"]
source_suffix = {".md": "myst-nb", ".ipynb": "myst-nb"}
root_doc = "index"
exclude_patterns = ["_build", "**/.ipynb_checkpoints", "**/exoplanet-inputs"]
myst_heading_anchors = 3
myst_enable_extensions = ["dollarmath"]
myst_fence_as_directive = ["mermaid"]
html_theme = "sphinx_rtd_theme"
html_title = "AtRIS documentation"
# Page order in the contents is not a workflow sequence. Use explicit step
# links within pages instead of the theme's automatic previous/next buttons.
html_theme_options = {"navigation_depth": 3, "prev_next_buttons_location": None}

# Execute examples in isolation; fail the build if a notebook fails.
nb_execution_mode = "force"
nb_execution_in_temp = True
nb_execution_timeout = 120
nb_execution_raise_on_error = True
