import importlib

import pytest


ENTRY_POINT_HELP = (
    (
        "atris-version",
        "version_command",
        ("no simulation is run", "geant4 runtime is not validated"),
    ),
    (
        "atris-nrlmsis-to-psf",
        "nrlmsis2psf",
        ("does not download atmosphere data", "replacing that file"),
    ),
    (
        "atris-psf-to-gdml",
        "psf2gdml",
        ("uses fixed filenames", "does not run atris"),
    ),
    (
        "atris-generate-macros",
        "atrismacrogen",
        ("does not run atris", "refuses to overwrite"),
    ),
    (
        "atris-stage-phantoms",
        "phantoms",
        ("does not create phantom responses", "not overwritten"),
    ),
    (
        "atris-clone",
        "clone_run",
        ("simulation results", "does not run or scatter"),
    ),
    (
        "atris-scatter",
        "scatter",
        ("does not repartition existing work", "does not run or gather"),
    ),
    (
        "atris-run",
        "run_chunks",
        ("do not launch workers", "never interrupts a running chunk"),
    ),
    (
        "atris-gather",
        "gather",
        ("partial files", "does not run missing chunks"),
    ),
    (
        "atris-postprocess",
        "postprocess",
        ("replacing existing processed files", "does not gather chunk histograms"),
    ),
    (
        "atris-plot",
        "plotting",
        ("missing product groups are skipped", "does not run atris"),
    ),
    (
        "atris-bin-to-ascii",
        "bin2asci",
        ("binary input is retained", "does not gather chunks"),
    ),
    (
        "nrlmsis2psf",
        "nrlmsis2psf",
        ("does not download atmosphere data",),
    ),
    ("psf2gdml", "psf2gdml", ("uses fixed filenames",)),
    ("atrismacrogen", "atrismacrogen", ("refuses to overwrite",)),
    ("postprocess", "postprocess", ("does not gather chunk histograms",)),
    ("bin2ascii", "bin2asci", ("binary input is retained",)),
)


@pytest.mark.parametrize(("command", "module_name", "expected"), ENTRY_POINT_HELP)
def test_entry_point_help_explains_scope(
    command, module_name, expected, monkeypatch, capsys
):
    module = importlib.import_module("atris_tools." + module_name)
    monkeypatch.setattr("sys.argv", [command, "--help"])

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.lower().split())
    assert help_text.startswith("usage: " + command)
    for text in expected:
        assert text in help_text
