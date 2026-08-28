import subprocess

import pytest

from atris_tools.run_chunks import (
    incomplete_entry_numbers,
    main,
    run_chunks,
    select_entries,
)


def prepare_run(tmp_path, plan=None):
    (tmp_path / "chunks").mkdir()
    if plan is None:
        plan = [
            ("protons", "111111", "222222"),
            ("alphas", "333333", "444444"),
        ]
    (tmp_path / "chunks.txt").write_text(
        "".join("%s %s %s\n" % entry for entry in plan)
    )
    (tmp_path / "phantoms.txt").write_text(
        "0 first 1.0 2.0\n"
        "1 second 3.0 4.0\n"
    )


def test_run_chunks_executes_plan_and_marks_success(tmp_path, monkeypatch):
    prepare_run(tmp_path)
    calls = []

    def fake_run(command, cwd, stdout, stderr, check):
        calls.append((command, cwd, stdout.name, stderr, check))

    monkeypatch.setattr("atris_tools.run_chunks.subprocess.run", fake_run)

    assert run_chunks(tmp_path) == 2
    assert calls == [
        (
            ["AtRIS", "FTFP_BERT_HP", "chunks/protons_111111_222222", "-1", "2"],
            tmp_path.resolve(),
            str(tmp_path / "chunks/protons_111111_222222.log"),
            subprocess.STDOUT,
            True,
        ),
        (
            ["AtRIS", "FTFP_BERT_HP", "chunks/alphas_333333_444444", "-1", "2"],
            tmp_path.resolve(),
            str(tmp_path / "chunks/alphas_333333_444444.log"),
            subprocess.STDOUT,
            True,
        ),
    ]
    assert (tmp_path / "chunks/protons_111111_222222.COMPLETE").is_file()
    assert (tmp_path / "chunks/alphas_333333_444444.COMPLETE").is_file()


def test_run_chunks_skips_complete_entries(tmp_path, monkeypatch):
    prepare_run(tmp_path)
    (tmp_path / "chunks/protons_111111_222222.COMPLETE").touch()
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path) == 1
    assert calls == [
        ["AtRIS", "FTFP_BERT_HP", "chunks/alphas_333333_444444", "-1", "2"]
    ]


def test_run_chunks_can_select_one_plan_entry(tmp_path, monkeypatch):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path, entry=2) == 1
    assert calls == [
        ["AtRIS", "FTFP_BERT_HP", "chunks/alphas_333333_444444", "-1", "2"]
    ]
    assert not (tmp_path / "chunks/protons_111111_222222.COMPLETE").exists()


def test_run_chunks_does_not_mark_failed_entry(tmp_path, monkeypatch):
    prepare_run(tmp_path)

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("atris_tools.run_chunks.subprocess.run", fail)

    with pytest.raises(subprocess.CalledProcessError):
        run_chunks(tmp_path, entry=1)

    assert not (tmp_path / "chunks/protons_111111_222222.COMPLETE").exists()


def test_select_entries_assigns_disjoint_round_robin_worker_shards():
    entries = [
        ("protons", "%06i" % number, "%06i" % (number + 100))
        for number in range(1, 8)
    ]

    shards = [
        select_entries(entries, worker_index=index, worker_count=3)
        for index in range(3)
    ]

    assert [[line for line, _ in shard] for shard in shards] == [
        [1, 4, 7],
        [2, 5],
        [3, 6],
    ]
    assert sorted(line for shard in shards for line, _ in shard) == list(range(1, 8))


@pytest.mark.parametrize(
    ("worker_index", "worker_count", "message"),
    [
        (0, 0, "at least 1"),
        (-1, 2, "between 0 and 1"),
        (2, 2, "between 0 and 1"),
    ],
)
def test_select_entries_rejects_invalid_worker_coordinates(
    worker_index, worker_count, message
):
    with pytest.raises(ValueError, match=message):
        select_entries([], worker_index=worker_index, worker_count=worker_count)


def test_run_chunks_executes_only_the_workers_shard(tmp_path, monkeypatch):
    plan = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
        ("alphas", "555555", "666666"),
        ("alphas", "777777", "888888"),
    ]
    prepare_run(tmp_path, plan)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path, worker_index=1, worker_count=2) == 2
    assert calls == [
        ["AtRIS", "FTFP_BERT_HP", "chunks/protons_333333_444444", "-1", "2"],
        ["AtRIS", "FTFP_BERT_HP", "chunks/alphas_777777_888888", "-1", "2"],
    ]


def test_run_chunks_stops_before_the_job_deadline(tmp_path, monkeypatch, capsys):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(
        tmp_path,
        deadline=1000,
        stop_before_end=100,
        clock=lambda: 900,
    ) == 0

    assert calls == []
    assert "wall-time safety window has begun" in capsys.readouterr().out


def test_main_defaults_to_one_scheduler_neutral_worker(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "sys.argv",
        ["atris-run", str(tmp_path)],
    )
    monkeypatch.setattr(
        "atris_tools.run_chunks.run_chunks",
        lambda *args, **kwargs: calls.append((args, kwargs)) or 0,
    )

    assert main() == 0
    assert calls == [
        (
            (tmp_path,),
            {
                "physics_list": "FTFP_BERT_HP",
                "mode": -1,
                "entry": None,
                "worker_index": 0,
                "worker_count": 1,
                "deadline": None,
                "stop_before_end": 0,
            },
        )
    ]


def test_incomplete_entry_numbers_uses_completion_markers(tmp_path):
    prepare_run(tmp_path)
    (tmp_path / "chunks/protons_111111_222222.COMPLETE").touch()

    assert incomplete_entry_numbers(tmp_path) == [2]
