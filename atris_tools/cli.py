"""Unified command-line interface for the AtRIS Python tools."""

import argparse
from importlib import import_module
from importlib.metadata import version
import os
import subprocess
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


def versions_match(tools_version, executable_version):
    executable_version = executable_version.lstrip("v")
    if "-g" not in executable_version:
        return tools_version == executable_version

    executable_commit = executable_version.rsplit("-g", 1)[1].split("-", 1)[0]
    if "+g" not in tools_version:
        return False
    tools_commit = tools_version.split("+g", 1)[1].split(".", 1)[0]
    return tools_commit.startswith(executable_commit)


def warn_version_mismatch(tools_version):
    executable = os.environ.get("ATRIS_EXECUTABLE")
    if not executable:
        return

    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None

    output = result.stdout.strip() if result is not None else ""
    if result is None or result.returncode != 0 or not output.startswith("AtRIS "):
        print("Warning: could not determine the AtRIS executable version.", file=sys.stderr)
        return

    executable_version = output[len("AtRIS "):]
    if not versions_match(tools_version, executable_version):
        print(
            "Warning: atris-tools " + tools_version
            + " does not match AtRIS " + executable_version + ".",
            file=sys.stderr,
        )


def make_parser():
    parser = argparse.ArgumentParser(
        prog="atris",
        description="Prepare, manage, and post-process AtRIS simulations.",
    )
    parser.add_argument("--version", action="store_true", help="show version information")
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

    tools_version = version("atris-tools")
    if argv == ["--version"]:
        print("atris-tools " + tools_version)
        warn_version_mismatch(tools_version)
        return 0

    command = argv[0]
    if command not in COMMANDS:
        parser.error("unknown command: " + command)

    warn_version_mismatch(tools_version)
    _, module_name, function_name = COMMANDS[command]
    command_main = getattr(import_module(module_name), function_name)
    return command_main(argv[1:], prog="atris " + command)


if __name__ == "__main__":
    sys.exit(main())
