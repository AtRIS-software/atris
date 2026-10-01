# atris-bin-to-ascii

Convert interface records to the historical five-column text format.

```bash
atris-bin-to-ascii protons.binary
atris-bin-to-ascii protons.binary -o crossings.txt
```

**Input:** a versioned or legacy headerless interface binary. Step files are
rejected. **Output:** the input basename with `.ascii`, or the `-o` path; an
existing output is replaced and the binary input is retained.

Columns are PDG code, interface ID, angle in degrees, kinetic energy in MeV,
and primary energy in MeV. There is no header; values are space-separated,
with integer first three fields and six decimal places for energies. The
converter creates an in-memory five-column array. For large files or CSV with
field names, use `atris-dump` instead.

The converter prints progress and min/max diagnostics and has no quiet/verbose
flags. Empty interface files currently fail during those min/max diagnostics,
even though the empty text output may already have been written.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-bin-to-ascii [-h] [-o ASCII_FILE] [--version] BINARY_FILE

Convert native AtRIS mode-0 particle-interface records from binary to the historical
five-column ASCII format.

positional arguments:
  BINARY_FILE           AtRIS mode-0 binary file to convert.

optional arguments:
  -h, --help            show this help message and exit
  -o ASCII_FILE, --output ASCII_FILE
                        ASCII file to write (default: input basename with .ascii
                        suffix).
  --version             Show the AtRIS and atris-tools versions and exit.

The output defaults to the input basename with an .ascii suffix, replacing an existing
file. The binary input is retained. This command does not gather chunks, post-process
response histograms, or make plots; the binary representation remains faster and
smaller for normal analysis.
```

Implementation: `atris_tools/bin2ascii.py`.
