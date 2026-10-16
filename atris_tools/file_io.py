"""Atomic replacement for text files written by AtRIS tools."""

from contextlib import contextmanager
import os
import tempfile


@contextmanager
def atomic_text_output(path):
    """Yield a temporary text file and replace path after a successful write."""
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_name = output.name
            yield output
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)
