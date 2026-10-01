# Python commands

Commands are installed by the `atris-tools` package. Paths and defaults below
refer to this revision. Each page includes inputs, outputs, overwrite behaviour,
and the command's full help text.

```{toctree}
:maxdepth: 1

atris-nrlmsis-to-psf
atris-psf-to-gdml
atris-generate-macros
atris-stage-phantoms
atris-clone
atris-scatter
atris-run
atris-gather
atris-postprocess
atris-plot
atris-dump
```

## Shared options

All modern commands accept `-h`/`--help` and `--version`. Most also accept
`--quiet` and `--verbose`; each command's help lists the supported options.
See [logging and version reporting](../runtime.md#logging-and-version-reporting)
for their behavior.

## Legacy command aliases

| Alias | Modern command |
| --- | --- |
| `nrlmsis2psf` | `atris-nrlmsis-to-psf` |
| `psf2gdml` | `atris-psf-to-gdml` |
| `atrismacrogen` | `atris-generate-macros` |
| `postprocess` | `atris-postprocess` |

Aliases invoke the same entry points, but only modern names receive the shared
`--version` option. Prefer modern names in new scripts.

The installed entry points are defined in `pyproject.toml` under
`[project.scripts]`.
