"""Unified command-line interface for the AtRIS Python tools."""

import argparse
from importlib import import_module
import sys


COMMANDS = {
    "nrlmsis-to-psf": (
        "Convert a downloaded NRLMSIS atmosphere to PSF.",
        "atris_tools.nrlmsis2psf",
        "main",
    ),
    "psf-to-gdml": (
        "Convert simulation.psf to simulation.gdml.",
        "atris_tools.simtools",
        "psf2gdml_main",
    ),
    "generate-macros": (
        "Generate proton and alpha inputs.",
        "atris_tools.atrismacrogen",
        "main",
    ),
    "gather": (
        "Gather completed chunk outputs.",
        "atris_tools.gather",
        "main",
    ),
    "postprocess": (
        "Post-process AtRIS histogram output.",
        "atris_tools.postprocess",
        "main",
    ),
    "bin-to-ascii": (
        "Convert AtRIS binary output to ASCII.",
        "atris_tools.bin2asci",
        "main",
    ),
}


def make_parser():
    parser = argparse.ArgumentParser(
        prog="atris",
        description="Prepare, manage, and post-process AtRIS simulations.",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    for name, command in COMMANDS.items():
        commands.add_parser(name, help=command[0], add_help=False)
    return parser


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = make_parser()
    if not argv or argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0

    command = argv[0]
    if command not in COMMANDS:
        parser.error("unknown command: " + command)

    _, module_name, function_name = COMMANDS[command]
    command_main = getattr(import_module(module_name), function_name)
    return command_main(argv[1:], prog="atris " + command)


if __name__ == "__main__":
    sys.exit(main())
