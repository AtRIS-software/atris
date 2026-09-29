import os

import pytest

from atris_tools.phantoms import stage_phantoms


def make_archive(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    for name in ("first", "second"):
        (archive / (name + "_response.txt")).write_text(name + " radiation\n")
        (archive / (name + "_counting.txt")).write_text(name + " counting\n")
    return archive


def write_phantoms(
    run_directory,
    rows=(
        "0  first    1.5  2.5\n"
        "1  second  30.5 40.5\n"
    ),
):
    contents = "# ID  Phantom  mass [g]  area [cm2]\n" + rows
    (run_directory / "phantoms.txt").write_text(contents)
    return contents


def test_stage_phantoms_uses_ids_independently_of_row_order(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    metadata = write_phantoms(
        run_directory,
        "1  second  30.5 40.5\n"
        "0  first   10.5 20.5\n",
    )

    count = stage_phantoms(run_directory, archive)

    assert count == 2
    radiation_zero = run_directory / "radiation_phantom0.txt"
    counting_one = run_directory / "counting_phantom1.txt"
    assert radiation_zero.is_symlink()
    assert counting_one.is_symlink()
    assert not os.path.isabs(os.readlink(radiation_zero))
    assert radiation_zero.read_text() == "first radiation\n"
    assert counting_one.read_text() == "second counting\n"
    assert (run_directory / "phantoms.txt").read_text() == metadata


def test_stage_phantoms_can_copy_files(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "0  first  1.5 2.5\n",
    )

    stage_phantoms(run_directory, archive, copy=True)

    local_radiation = run_directory / "first_response.txt"
    local_counting = run_directory / "first_counting.txt"
    radiation = run_directory / "radiation_phantom0.txt"
    counting = run_directory / "counting_phantom0.txt"
    assert local_radiation.is_file()
    assert local_counting.is_file()
    assert not local_radiation.is_symlink()
    assert not local_counting.is_symlink()
    assert radiation.is_symlink()
    assert counting.is_symlink()
    assert os.readlink(radiation) == "first_response.txt"
    assert os.readlink(counting) == "first_counting.txt"
    assert radiation.read_text() == "first radiation\n"


def test_stage_phantoms_copy_replaces_matching_links(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "0  first  1.5 2.5\n",
    )
    stage_phantoms(run_directory, archive)

    stage_phantoms(run_directory, archive, copy=True)
    stage_phantoms(run_directory, archive, copy=True)

    local_radiation = run_directory / "first_response.txt"
    local_counting = run_directory / "first_counting.txt"
    radiation = run_directory / "radiation_phantom0.txt"
    counting = run_directory / "counting_phantom0.txt"
    assert local_radiation.is_file()
    assert local_counting.is_file()
    assert not local_radiation.is_symlink()
    assert not local_counting.is_symlink()
    assert radiation.is_symlink()
    assert counting.is_symlink()
    assert os.readlink(radiation) == "first_response.txt"
    assert os.readlink(counting) == "first_counting.txt"
    assert radiation.read_text() == "first radiation\n"
    assert counting.read_text() == "first counting\n"


def test_stage_phantoms_accepts_custom_files_in_run_directory(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    (run_directory / "custom_response.txt").write_text("custom radiation\n")
    (run_directory / "custom_counting.txt").write_text("custom counting\n")
    write_phantoms(
        run_directory,
        "0  custom  7.5 8.5\n",
    )

    stage_phantoms(run_directory)

    assert (run_directory / "radiation_phantom0.txt").read_text() == (
        "custom radiation\n"
    )
    assert (run_directory / "counting_phantom0.txt").read_text() == (
        "custom counting\n"
    )


def test_stage_phantoms_accepts_run_without_phantoms(tmp_path):
    run_directory = tmp_path / "run"
    run_directory.mkdir()

    assert stage_phantoms(run_directory) == 0
    assert list(run_directory.iterdir()) == []


def test_stage_phantoms_refuses_all_destinations_before_writing(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    metadata = write_phantoms(run_directory)
    existing = run_directory / "counting_phantom1.txt"
    existing.write_text("keep me\n")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        stage_phantoms(run_directory, archive)

    assert existing.read_text() == "keep me\n"
    assert not (run_directory / "radiation_phantom0.txt").exists()
    assert (run_directory / "phantoms.txt").read_text() == metadata


def test_stage_phantoms_checks_all_sources_before_writing(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    metadata = write_phantoms(run_directory)
    (archive / "second_counting.txt").unlink()

    with pytest.raises(FileNotFoundError, match="second_counting.txt"):
        stage_phantoms(run_directory, archive)

    assert list(run_directory.iterdir()) == [run_directory / "phantoms.txt"]
    assert (run_directory / "phantoms.txt").read_text() == metadata


def test_stage_phantoms_rejects_missing_file(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "0  missing  1.5 2.5\n",
    )

    with pytest.raises(FileNotFoundError, match="missing_response.txt"):
        stage_phantoms(run_directory, archive)

    assert list(run_directory.iterdir()) == [run_directory / "phantoms.txt"]


@pytest.mark.parametrize(
    "rows",
    (
        "0  first  1.5 2.5\n0  second  3.5 4.5\n",
        "1  first  1.5 2.5\n",
    ),
)
def test_stage_phantoms_rejects_duplicate_or_gapped_ids(tmp_path, rows):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, rows)

    with pytest.raises(ValueError, match="unique and contiguous"):
        stage_phantoms(run_directory, archive)

    assert list(run_directory.iterdir()) == [run_directory / "phantoms.txt"]
