# atris-dump

Stream an interface or step ntuple from AtRIS ROOT output as CSV.

```bash
atris-dump protons.root interfaces | head
atris-dump protons.root steps > protons.steps.csv
```

Choose `interfaces` for the mode-0/mode-1 crossing records or `steps` for the
mode-1 transport trace. Output starts with the field-name header. The ROOT file
is read incrementally and is not modified; early pipe closure is handled, so
the command can be used with `head`. Shell redirection controls whether a CSV
file is created or replaced. There are no quiet/verbose flags.

See the [ROOT ntuple schemas](root-output) for field
definitions.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-dump [-h] [--version] ROOT_FILE {interfaces,steps}

Dump an AtRIS interface or transport-step ROOT ntuple as CSV text on standard
output.

positional arguments:
  ROOT_FILE           AtRIS mode-0 or mode-1 ROOT file to read.
  {interfaces,steps}  ROOT ntuple to dump.

optional arguments:
  -h, --help          show this help message and exit
  --version           Show the AtRIS and atris-tools versions and exit.

The ROOT file is read incrementally and is not modified. Pipe the output to
tools such as head or redirect it to a text file.
```

Implementation: `atris_tools/dump.py`.
