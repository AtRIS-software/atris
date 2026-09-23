"""Shared command-line behavior for the AtRIS Python tools."""

import argparse
import logging
import sys
import textwrap

try:
    import colorlog
except ImportError:
    colorlog = None


class HelpFormatter(argparse.HelpFormatter):
    """Use argparse wrapping without splitting words or option names."""

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(" ", text).strip()
        return textwrap.wrap(
            text,
            width,
            break_long_words=False,
            break_on_hyphens=False,
        )

    def _fill_text(self, text, width, indent):
        rendered = []
        for line in text.splitlines():
            if not line.strip():
                rendered.append("")
                continue
            leading_space = line[: len(line) - len(line.lstrip())]
            line_indent = indent + leading_space
            line = self._whitespace_matcher.sub(" ", line).strip()
            rendered.append(
                textwrap.fill(
                    line,
                    width,
                    initial_indent=line_indent,
                    subsequent_indent=line_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        return "\n".join(rendered)


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
    if sys.stderr.isatty():
        plain_format = "%(message)s"
        log_format = "%(log_color)s%(message)s%(reset)s"
    else:
        plain_format = "%(levelname)s %(message)s"
        log_format = "%(log_color)s%(levelname)s %(message)s%(reset)s"
    if colorlog is None:
        logging.basicConfig(
            level=level,
            stream=sys.stderr,
            format=plain_format,
        )
        return
    log_colors = {
        "DEBUG": "cyan",
        "INFO": "",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
    colorlog.basicConfig(
        level=level,
        stream=sys.stderr,
        format=log_format,
        log_colors=log_colors,
    )
