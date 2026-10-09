from pathlib import Path
import shutil

import numpy as np
import pytest

from atris_tools.phantom_tables import (
    PhantomTable,
    ENERGY_CENTRES_MEV,
    COUNTING_EFFICIENCY,
)

ARCHIVE = Path(__file__).parents[2] / "phantoms"


def test_radiation_values_are_unchanged_regardless_of_unit_comment(tmp_path):
    fractions = np.vstack([np.linspace(0, 1, 650), np.linspace(2, 0, 650)])
    table = PhantomTable(np.array([22, 2212]), fractions)
    table.write(tmp_path / "fractions.txt")
    np.savetxt(
        tmp_path / "mev.txt",
        table.deposited_energy_MeV,
        header="22 2212\n# atris_quantity: deposited_energy_MeV",
        comments="",
    )
    for name, expected in [("fractions.txt", fractions), ("mev.txt", table.deposited_energy_MeV)]:
        read = PhantomTable.read(tmp_path / name)
        np.testing.assert_array_equal(read.coefficients, expected)
        np.testing.assert_allclose(
            read.deposited_energy_MeV, expected * ENERGY_CENTRES_MEV
        )


@pytest.mark.parametrize(
    "path", sorted(ARCHIVE.rglob("*response.txt")), ids=lambda p: p.name
)
def test_legacy_tables_remain_readable_when_renamed(tmp_path, path):
    renamed = tmp_path / "radiation_phantom0.txt"
    shutil.copyfile(path, renamed)
    table = PhantomTable.read(renamed)
    raw = np.loadtxt(path, skiprows=1)
    np.testing.assert_array_equal(table.coefficients, raw)


def test_untagged_response_needs_no_catalogue_or_unit_declaration(tmp_path):
    path = tmp_path / "response.txt"
    np.savetxt(path, np.ones((1, 650)), header="22", comments="")
    np.testing.assert_array_equal(PhantomTable.read(path).coefficients, 1)
    counting = PhantomTable.read(path, counting=True)
    assert counting.quantity == COUNTING_EFFICIENCY
    counting.write(path)
    np.testing.assert_array_equal(
        PhantomTable.read(path, counting=True).coefficients, 1
    )


@pytest.mark.parametrize(
    "quantity", ["mystery", "energy_fraction\n# atris_quantity: energy_fraction"]
)
def test_quantity_comments_do_not_control_reading(tmp_path, quantity):
    path = tmp_path / "response.txt"
    np.savetxt(
        path, np.ones((1, 650)), header=f"22\n# atris_quantity: {quantity}", comments=""
    )
    np.testing.assert_array_equal(PhantomTable.read(path).coefficients, 1)


def test_counting_probability_and_row_shape_are_checked():
    with pytest.raises(ValueError, match="650"):
        PhantomTable(np.array([22]), np.ones((1, 649)))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        PhantomTable(np.array([22]), np.full((1, 650), 1.1), COUNTING_EFFICIENCY)


def test_comment_header_and_metadata_round_trip(tmp_path):
    path = tmp_path / "response.txt"
    table = PhantomTable(
        np.array([22, 2212]),
        np.full((2, 650), 0.25),
        metadata={"radius_cm": "0.0004", "material": "liquid water"},
    )
    table.write(path)
    assert path.read_text().startswith("# AtRIS phantom table\n")
    read = PhantomTable.read(path)
    np.testing.assert_array_equal(read.pdg_codes, table.pdg_codes)
    np.testing.assert_array_equal(read.coefficients, table.coefficients)
    assert read.metadata["radius_cm"] == "0.0004"
    assert read.metadata["energy_log10_step"] == "0.02"
    assert read.metadata["coefficient_unit"] == "1 (dimensionless)"
    read.write(path)
    assert PhantomTable.read(path).metadata == read.metadata


def test_comments_do_not_change_coefficients(tmp_path):
    path = ARCHIVE / "MeV-valued" / "icru_zero_0.000MeV_detAB_response.txt"
    original = PhantomTable.read(path)
    lines = path.read_text().splitlines(keepends=True)
    lines.insert(3, "# An explanatory comment between particle rows.\n")
    annotated = tmp_path / "annotated.txt"
    annotated.write_text(
        "# Historical table; generation settings unknown.\n" + "".join(lines)
    )
    read = PhantomTable.read(annotated)
    np.testing.assert_array_equal(read.coefficients, original.coefficients)


def test_comments_without_particle_data_are_rejected(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("# AtRIS phantom table\n\n# radius_cm: 0.0004\n")
    with pytest.raises(ValueError, match="Missing PDG"):
        PhantomTable.read(path)


def test_wrapped_coefficients_follow_cpp_particle_order(tmp_path):
    values = np.arange(1300, dtype=float)
    path = tmp_path / "wrapped.txt"
    path.write_text(
        "# Informational header\n22 2212 # particle codes\n"
        + "\n".join(
            " ".join(map(str, values[start:start + 13])) + " # row fragment"
            for start in range(0, values.size, 13)
        )
    )
    table = PhantomTable.read(path)
    np.testing.assert_array_equal(table.coefficients, values.reshape(2, 650))


@pytest.mark.parametrize("quantity", ["energy_fraction", "deposited_energy_MeV"])
def test_plot_uses_cpp_fraction_convention_regardless_of_comments(tmp_path, monkeypatch, quantity):
    from matplotlib.figure import Figure
    from atris_tools.input_plotting import plot_phantom_inputs

    monkeypatch.chdir(tmp_path)
    fractions = np.full((2, 650), 0.5)
    values = (
        fractions if quantity == "energy_fraction" else fractions * ENERGY_CENTRES_MEV
    )
    np.savetxt(
        "radiation_phantom0.txt",
        values,
        header=f"22 1000060120\n# atris_quantity: {quantity}",
        comments="",
    )
    PhantomTable(np.array([22, 1000060120]), fractions, COUNTING_EFFICIENCY).write(
        "counting_phantom0.txt"
    )
    figures = []
    monkeypatch.setattr(Figure, "savefig", lambda figure, *args: figures.append(figure))
    plot_phantom_inputs(0, "test")
    assert len(figures[0].axes) == 4
    for axis in figures[0].axes[2:]:
        np.testing.assert_allclose(axis.lines[0].get_ydata(), ENERGY_CENTRES_MEV)
        np.testing.assert_allclose(axis.lines[1].get_ydata(), values[0] * ENERGY_CENTRES_MEV)
