import argparse
import importlib
import logging
import sys

import pytest
import colorlog

from atris_tools.cli import add_logging_arguments, configure_logging


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
    monkeypatch.setattr(
        colorlog,
        "basicConfig",
        lambda **values: options.update(values),
    )

    configure_logging(logging.DEBUG)

    assert options == {"level": logging.DEBUG, "stream": sys.stderr}


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
