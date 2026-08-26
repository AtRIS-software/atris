"""Report the Python tools and C++ executable versions."""

import argparse
from importlib.metadata import version
import subprocess
import sys


def versions_match(tools_version, executable_version):
    return tools_version == executable_version


def main():
    parser = argparse.ArgumentParser(
        description="Show the atris-tools and AtRIS versions."
    )
    parser.parse_args()

    tools_version = version("atris-tools")
    print("atris-tools " + tools_version)

    try:
        result = subprocess.run(
            ["AtRIS", "--version"],
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

    print(output)
    executable_version = output[len("AtRIS "):]
    if not versions_match(tools_version, executable_version):
        print(
            "Warning: atris-tools " + tools_version
            + " does not match AtRIS " + executable_version + ".",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
