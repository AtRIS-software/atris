"""Shared command-line behavior for the AtRIS Python tools."""

import logging
import os
import sys

import colorlog


def add_logging_arguments(parser):
    """Add the standard quiet and verbose options to a command parser."""
    levels = parser.add_mutually_exclusive_group()
    levels.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=logging.WARNING,
        dest="log_level",
        help="Suppress normal progress; show warnings and errors only.",
    )
    levels.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=logging.DEBUG,
        dest="log_level",
        help="Include detailed per-file, per-request, or per-chunk progress.",
    )
    parser.set_defaults(log_level=logging.INFO)


def configure_logging(level):
    """Configure colored command-line logging at the requested level."""
    color = "FORCE_COLOR" in os.environ or (
        "NO_COLOR" not in os.environ and sys.stderr.isatty()
    )
    if color:
        log_format = "%(log_color)s%(module)s%(reset)s: %(message)s"
    else:
        log_format = "%(levelname)s %(module)s: %(message)s"
    colorlog.basicConfig(level=level, stream=sys.stderr, format=log_format)
