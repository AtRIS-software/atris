"""Report the Python tools and C++ executable versions."""

import argparse
from importlib.metadata import version
import subprocess
import sys


def versions_match(tools_version, executable_version):
    executable_version = executable_version.lstrip("v")
    if "-g" not in executable_version:
        return tools_version == executable_version

    executable_commit = executable_version.rsplit("-g", 1)[1].split("-", 1)[0]
    if "+g" not in tools_version:
        return False
    tools_commit = tools_version.split("+g", 1)[1].split(".", 1)[0]
    return tools_commit.startswith(executable_commit)


def main():
    parser = argparse.ArgumentParser(
        description="Show the AtRIS and atris-tools versions and compare their source revisions."
    )
    parser.parse_args()

    tools_version = version("atris-tools")

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
        print("AtRIS executable version: unavailable")
        print("atris-tools version: " + tools_version)
        print("Warning: could not determine the AtRIS executable version.", file=sys.stderr)
        return

    executable_version = output[len("AtRIS "):]
    print("AtRIS executable version: " + executable_version)
    print("atris-tools version: " + tools_version)
    if not versions_match(tools_version, executable_version):
        print(
            "Warning: the AtRIS executable was built from a different source "
            "revision (atris-tools " + tools_version
            + "; AtRIS " + executable_version + ").",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
