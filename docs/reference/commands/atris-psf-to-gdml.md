# atris-psf-to-gdml

Convert a PSF into GDML geometry and materials.

**Input:** a PSF model. **Output:** the input basename with `.gdml`, or `-o`.
An existing output is replaced. The converter uses the package's material
resources and does not require a running Geant4 installation.

```bash
atris-psf-to-gdml simulation.psf
```

See [PSF and GDML formats](../inputs.md). This tool does not provide the common
quiet/verbose logging flags.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-psf-to-gdml [-h] [-o GDML_FILE] [--version] PSF_FILE

Convert an AtRIS Planet Specification Format model into the GDML geometry and material
description read by Geant4.

positional arguments:
  PSF_FILE              PSF model to convert.

optional arguments:
  -h, --help            show this help message and exit
  -o GDML_FILE, --output GDML_FILE
                        GDML file to write (default: input basename with .gdml
                        suffix).
  --version             Show the AtRIS and atris-tools versions and exit.

The output defaults to the input basename with a .gdml suffix. An existing output file
is replaced. This command does not download or generate an atmosphere and does not run
AtRIS.
```

Implementation: `atris_tools/psf2gdml.py`.
