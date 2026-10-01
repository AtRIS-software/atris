# AtRIS executable

```text
AtRIS <physics-list> <simulation-name> <mode> <phantom-count>
AtRIS --version
```

All four positional arguments are required for a simulation. Run from the
directory containing its inputs and numbered phantom files.

| Argument | Meaning |
| --- | --- |
| `physics-list` | Geant4 reference physics-list name, for example `FTFP_BERT_HP`. Availability depends on the linked Geant4 installation. An unrecognized name prints the available reference lists and exits unsuccessfully. |
| `simulation-name` | Input and output prefix, or a seeded chunk name as described below. |
| `mode` | Integer output mode from the table below. The executable does not accept the Python runner's mode names. |
| `phantom-count` | Number of phantom pairs to load, indexed from zero. Use `0` for no phantom responses. This argument does not read `phantoms.txt`. |

```bash
AtRIS FTFP_BERT_HP protons -1 2
```

This reads `protons.gdml`, `protons.bins`, `protons.mac`, and the two numbered
phantom pairs in the current directory. Files beginning with `protons` receive
the outputs. Existing output names can be overwritten.

## Output modes

| Integer | Name used by `atris-run` | Products |
| --- | --- | --- |
| `-1` | `response` | Primary, source-position, source-direction, ionization, and phantom CSV histograms. |
| `0` | `profile` | All histograms plus `<name>.binary` interface-crossing records. |
| `1` | `shower` | All histograms and interface records, plus `<name>.steps.binary` records for steps in sensitive volumes. |

Use only these three modes. Other integers are not explicitly rejected but
have no documented contract. Step output includes steps in the terminating
sensitive layers, before the track is killed; it does not record steps in
non-sensitive world space. See [Output files](outputs.md) for schemas.

## Seeded chunk names

A basename ending in two underscore-separated, exactly six-digit decimal
fields is interpreted as `<prefix>_<seed1>_<seed2>`:

```bash
AtRIS FTFP_BERT_HP chunks/protons_123456_654321 -1 2
```

The full argument remains the output prefix. Input lookup uses the stripped
basename in the current directory: `protons.gdml`, `protons.bins`, and
`protons.chunk.mac` if it exists, otherwise `protons.mac`. The directory part
of a seeded name does not select an input directory. Both seeds are set before
the macro executes; a later `/random/setSeeds` command in that macro can
replace them. `atris-scatter` removes that command from generated chunk macros.

For an ordinary, unseeded name, its path is retained when locating inputs.
The parent directory of an output prefix must already exist.

## Status and diagnostics

`AtRIS --version` prints the compiled version. A successful macro execution
returns `0`; a failed macro execution returns `1`. Phantom loading and binary
opening failures also return `1`. Wrong argument count prints usage but
currently returns `0`, so a zero status alone is not evidence that a simulation
ran. Malformed integer arguments can fail before execution.

The executable writes diagnostics to standard output/error. It does not itself
create a `.log` file; `atris-run` redirects both streams to a per-chunk log.

At completion, AtRIS reports the wall time spent executing the Geant4 macro,
the setup and cleanup time outside that macro, and their total. The macro
interval uses the reported worker count but can still include serial Geant4
initialization, coordination, and output work; it is not pure parallel CPU
time.

Implementation: `src/main.cc`, `src/HistoManager.cc`, and
`src/SensitiveDetector.cc`.
