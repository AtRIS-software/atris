"""Shared command-line behavior for the AtRIS Python tools."""

import logging

from colorlog import ColoredFormatter


LOG_FORMAT = "[%(asctime)s] %(log_color)s%(levelname)s%(reset)s %(message)s"
LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


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
    """Configure concise colored logging for interactive terminals."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColoredFormatter(
            LOG_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors=LOG_COLORS,
            reset=False,
            stream=handler.stream,
        )
    )
    logging.basicConfig(
        level=level,
        handlers=[handler],
    )
