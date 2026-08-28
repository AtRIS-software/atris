import argparse
import importlib
import io
import logging
import sys

import pytest
from colorlog import ColoredFormatter

from atris_tools.cli import (
    LOG_COLORS,
    LOG_FORMAT,
    add_logging_arguments,
    configure_logging,
)


MODERN_COMMAND_MODULES = (
    "atrismacrogen",
    "clone_run",
    "gather",
    "nrlmsis2psf",
    "phantoms",
    "plotting",
    "postprocess",
    "run_chunks",
    "scatter",
)


class TtyStringIO(io.StringIO):
    def isatty(self):
        return True


def test_logging_arguments_default_to_info():
    parser = argparse.ArgumentParser()
    add_logging_arguments(parser)

    assert parser.parse_args([]).log_level == logging.INFO


def test_logging_arguments_select_quiet_or_verbose():
    parser = argparse.ArgumentParser()
    add_logging_arguments(parser)

    assert parser.parse_args(["--quiet"]).log_level == logging.WARNING
    assert parser.parse_args(["--verbose"]).log_level == logging.DEBUG


def test_configure_logging_uses_requested_level(monkeypatch):
    options = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **values: options.update(values))

    configure_logging(logging.DEBUG)

    assert options["level"] == logging.DEBUG
    assert len(options["handlers"]) == 1
    formatter = options["handlers"][0].formatter
    assert isinstance(formatter, ColoredFormatter)
    assert formatter._fmt == LOG_FORMAT
    assert formatter.datefmt == "%Y-%m-%d %H:%M:%S"
    assert formatter.log_colors == LOG_COLORS


def emit_configured_record(monkeypatch, tty=False, force_color=False, no_color=False):
    stream = TtyStringIO() if tty else io.StringIO()
    options = {}
    monkeypatch.setattr(sys, "stderr", stream)
    monkeypatch.setattr(logging, "basicConfig", lambda **values: options.update(values))
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    if force_color:
        monkeypatch.setenv("FORCE_COLOR", "1")
    else:
        monkeypatch.delenv("FORCE_COLOR", raising=False)

    configure_logging(logging.INFO)
    record = logging.LogRecord("test", logging.INFO, "", 0, "message", (), None)
    options["handlers"][0].emit(record)
    return stream.getvalue()


def test_redirected_logging_is_plain(monkeypatch):
    output = emit_configured_record(monkeypatch)

    assert "\x1b[" not in output
    assert "INFO message" in output


def test_interactive_logging_is_colored(monkeypatch):
    output = emit_configured_record(monkeypatch, tty=True)

    assert "\x1b[" in output
    assert "INFO" in output


def test_no_color_disables_interactive_color(monkeypatch):
    output = emit_configured_record(monkeypatch, tty=True, no_color=True)

    assert "\x1b[" not in output
    assert "INFO message" in output


def test_force_color_colors_redirected_logging(monkeypatch):
    output = emit_configured_record(monkeypatch, force_color=True)

    assert "\x1b[" in output
    assert "INFO" in output
    assert output.endswith(" message\n")


@pytest.mark.parametrize("module_name", MODERN_COMMAND_MODULES)
def test_modern_commands_offer_standard_logging_options(
    module_name, monkeypatch, capsys
):
    module = importlib.import_module("atris_tools." + module_name)
    monkeypatch.setattr("sys.argv", [module_name, "--help"])

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "-q, --quiet" in help_text
    assert "-v, --verbose" in help_text
