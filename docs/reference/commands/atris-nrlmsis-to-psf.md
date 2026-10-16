# atris-nrlmsis-to-psf

Convert one or more downloaded NRLMSIS atmosphere tables into a PSF model.

**Inputs:** NASA CCMC text tables describing a common time and location.
**Output:** a PSF file; an existing destination is replaced. With one input,
the default is that input's basename with `.psf`. Multiple inputs require `-o`.

```bash
atris-nrlmsis-to-psf lower.txt upper.txt -o simulation.psf
```

See [NRLMSIS and PSF formats](../inputs.md). No atmosphere download occurs.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-nrlmsis-to-psf [-h] [-o PSF_FILE] [-q | -v] [--version] TABLE [TABLE ...]

Convert one or more NASA CCMC NRLMSIS text tables into the Planet Specification Format
(PSF) used by AtRIS.

positional arguments:
  TABLE                 Downloaded NRLMSIS text table. Supply multiple tables when the
                        altitude profile was downloaded in chunks.

optional arguments:
  -h, --help            show this help message and exit
  -o PSF_FILE, --output PSF_FILE
                        PSF file to write. Required when more than one input table is
                        supplied.
  -q, --quiet           Suppress normal progress; show warnings and errors only.
  -v, --verbose         Include detailed per-file, per-request, or per-chunk progress.
  --version             Show the AtRIS and atris-tools versions and exit.

Downloaded tables from NRLMSISE-00, NRLMSIS 2.0, and NRLMSIS 2.1 are supported. This
command does not download atmosphere data. Input tables may overlap and may be
supplied in any altitude order, but they must describe the same location and time and
combine into a complete, uniformly spaced altitude grid. With one input table, the
output defaults to the same basename with a .psf suffix. Multiple input tables require
--output. An existing output file is replaced.
```

Implementation: `atris_tools/nrlmsis.py`.
