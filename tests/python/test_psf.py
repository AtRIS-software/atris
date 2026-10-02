import numpy as np

from atris_tools.psf import load_psf, read_psf_header, read_psf_layers


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


def test_reads_psf_rows_as_material_layers(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "O750Si250 N O\n"
        "0 1 0 1 0 1 0 293 2.7 1 1 0 0\n"
        "1 2 0 1 0 1 1 250 0.1 2 2 0.25 0.75\n"
    )

    layers = read_psf_layers(path)

    assert [layer["state"] for layer in layers] == ["solid", "liquid"]
    assert layers[0]["fractions"] == {"O": 0.75, "Si": 0.25}
    assert layers[1]["fractions"] == {"N": 0.25, "O": 0.75}
    assert [layer["detector_id"] for layer in layers] == [0, 1]
