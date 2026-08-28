import os

import pytest

from atris_tools.clone_run import clone_run


def test_clone_run_copies_inputs_but_not_results(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for filename in (
        "simulation.psf",
        "simulation.gdml",
        "protons.mac",
        "protons.bins",
        "protons.gdml",
        "phantoms.txt",
        "custom_response.txt",
        "custom_counting.txt",
    ):
        (source / filename).write_text(filename + "\n")
    (source / "radiation_phantom0.txt").symlink_to("custom_response.txt")
    (source / "counting_phantom0.txt").symlink_to("custom_counting.txt")
    for filename in (
        "protons_h1_h1.1.csv",
        "protons.ioni",
        "protons.png",
        "protons.log",
        "chunks.txt",
    ):
        (source / filename).write_text("result\n")

    destination = tmp_path / "destination"
    copied = clone_run(source, destination)

    assert copied == sorted(
        (
            "counting_phantom0.txt",
            "custom_counting.txt",
            "custom_response.txt",
            "phantoms.txt",
            "protons.bins",
            "protons.gdml",
            "protons.mac",
            "radiation_phantom0.txt",
            "simulation.gdml",
            "simulation.psf",
        )
    )
    assert not (destination / "protons_h1_h1.1.csv").exists()
    assert not (destination / "protons.ioni").exists()
    assert not (destination / "protons.png").exists()
    assert not (destination / "protons.log").exists()
    assert not (destination / "chunks.txt").exists()

    radiation = destination / "radiation_phantom0.txt"
    assert radiation.is_symlink()
    assert not os.path.isabs(os.readlink(radiation))
    assert radiation.resolve() == destination / "custom_response.txt"


def test_clone_run_refuses_existing_destination(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "simulation.psf").write_text("input\n")
    destination = tmp_path / "destination"
    destination.mkdir()

    with pytest.raises(FileExistsError, match="Destination already exists"):
        clone_run(source, destination)

    assert list(destination.iterdir()) == []


def test_clone_run_rejects_directory_without_inputs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(ValueError, match="No AtRIS input files"):
        clone_run(source, tmp_path / "destination")

    assert not (tmp_path / "destination").exists()
