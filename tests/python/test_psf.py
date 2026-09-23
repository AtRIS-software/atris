import numpy as np

from atris_tools.psf import load_psf, read_psf_header


def test_reads_descriptive_header_followed_by_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "# Planet Specification Format\n"
        "# Column descriptions\n"
        "H1000 H\n"
        "0 1 0 1 0 1 0 293 1 1 1 0\n"
    )

    assert read_psf_header(path) == ["H1000", "H"]
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )


def test_reads_legacy_commented_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "#H1000 H\n"
        "0 1 0 1 0 1 0 293 1 1 1 0\n"
    )

    assert read_psf_header(path) == ["H1000", "H"]
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )
