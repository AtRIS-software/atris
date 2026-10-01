# atris-dump

Stream a binary interface or step file as CSV to standard output.

```bash
atris-dump protons.binary | head
atris-dump protons.steps.binary > protons.steps.csv
```

The binary input is unchanged. Output starts with the field-name header and
uses the [binary record fields](../outputs.md#binary-header). Record type is
detected from the header; historical headerless files are treated as interface
records. Files are memory-mapped and CSV rows are emitted incrementally. Early
pipe closure is handled, allowing use with `head`. Shell redirection controls
whether an output file is created or overwritten. There are no quiet/verbose
flags.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-dump [-h] [--version] BINARY_FILE

Dump an AtRIS interface or transport-step binary output file as CSV text on standard
output.

positional arguments:
  BINARY_FILE  AtRIS .binary or .steps.binary file to dump.

optional arguments:
  -h, --help   show this help message and exit
  --version    Show the AtRIS and atris-tools versions and exit.

The input file is not modified. Pipe the output to tools such as head or redirect it
to a text file. Headerless mode-0 interface files produced by earlier AtRIS versions
are also supported.
```

Implementation: `atris_tools/dump.py`.
