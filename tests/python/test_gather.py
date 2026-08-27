from pathlib import Path

import numpy as np
import pytest

from atris_tools.gather import (
    completed_prefixes,
    gather_histogram,
    gather_simulation,
    read_chunk_plan,
    read_histogram,
)


COLUMNS = "entries,Sw,Sw2,Sxw0,Sx2w0"


def write_histogram(path, rows, *, plane_sum=1.0, title="kinetic energy"):
    lines = [
        "#class tools::histo::h1d",
        f"#title {title}",
        "#dimension 1",
        f"#planes_Sxyw {plane_sum}",
        COLUMNS,
    ]
    lines.extend(",".join(str(value) for value in row) for row in rows)
    Path(path).write_text("\n".join(lines) + "\n")


def test_read_chunk_plan_reports_malformed_line_number(tmp_path):
    (tmp_path / "chunks.txt").write_text(
        "protons 123456 654321\n"
        "alphas only-two-fields\n"
    )

    with pytest.raises(ValueError, match=r"line 2$"):
        read_chunk_plan(tmp_path)


def test_completed_prefixes_require_marker_and_matching_species(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
        ("alphas", "555555", "666666"),
    ]
    (chunks / "protons_111111_222222.COMPLETE").touch()
    (chunks / "protons_333333_444444_partial.csv").write_text("unfinished\n")
    (chunks / "alphas_555555_666666.COMPLETE").touch()

    assert completed_prefixes(tmp_path, entries, "protons") == [
        chunks / "protons_111111_222222"
    ]


def test_gather_histogram_sums_all_columns_and_plane_values(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    write_histogram(first, [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]], plane_sum=2.5)
    write_histogram(second, [[10, 20, 30, 40, 50], [60, 70, 80, 90, 100]], plane_sum=4.0)

    total = gather_histogram([first, second], destination)

    np.testing.assert_array_equal(
        total,
        np.array([[11, 22, 33, 44, 55], [66, 77, 88, 99, 110]], dtype=float),
    )
    header, columns, written = read_histogram(destination)
    assert "#planes_Sxyw 6.5" in header
    assert columns == COLUMNS
    np.testing.assert_array_equal(written, total)

    first_result = destination.read_bytes()
    gather_histogram([first, second], destination)
    assert destination.read_bytes() == first_result


@pytest.mark.parametrize("difference", ["header", "shape", "columns"])
def test_gather_histogram_rejects_incompatible_input_without_replacing_destination(
    tmp_path, difference
):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    write_histogram(first, [[1, 2, 3, 4, 5]])

    if difference == "header":
        write_histogram(second, [[1, 2, 3, 4, 5]], title="different")
    elif difference == "shape":
        write_histogram(second, [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
    else:
        write_histogram(second, [[1, 2, 3, 4, 5]])
        second.write_text(second.read_text().replace(COLUMNS, "entries,Sw,other,Sxw0,Sx2w0"))

    destination.write_text("existing canonical output\n")
    with pytest.raises(ValueError):
        gather_histogram([first, second], destination)

    assert destination.read_text() == "existing canonical output\n"


def test_gather_simulation_uses_only_completed_chunks(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
    ]
    complete_prefix = chunks / "protons_111111_222222"
    unfinished_prefix = chunks / "protons_333333_444444"
    complete_prefix.with_name(complete_prefix.name + ".COMPLETE").touch()
    write_histogram(
        complete_prefix.with_name(complete_prefix.name + "_h1_h1.1.csv"),
        [[0, 0, 0, 0, 0], [3, 30, 300, 300, 3000]],
    )
    write_histogram(
        unfinished_prefix.with_name(unfinished_prefix.name + "_h1_h1.1.csv"),
        [[99, 99, 99, 99, 99]],
    )

    assert gather_simulation(tmp_path, entries, "protons") == 1

    _, _, data = read_histogram(tmp_path / "protons_h1_h1.1.csv")
    np.testing.assert_array_equal(
        data,
        np.array([[0, 0, 0, 0, 0], [3, 30, 300, 300, 3000]], dtype=float),
    )
    assert not (tmp_path / "alphas_h1_h1.1.csv").exists()


def test_gather_simulation_with_no_complete_chunks_writes_nothing(tmp_path):
    (tmp_path / "chunks").mkdir()

    assert gather_simulation(
        tmp_path, [("alphas", "123456", "654321")], "alphas"
    ) == 0
    assert list(tmp_path.glob("alphas_*.csv")) == []
