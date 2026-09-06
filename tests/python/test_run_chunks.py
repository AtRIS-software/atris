import logging
import subprocess

import pytest

from atris_tools.run_chunks import (
    incomplete_entry_numbers,
    main,
    normalize_output_mode,
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


def test_run_chunks_keeps_default_progress_under_ten_lines(
    tmp_path, monkeypatch, caplog
):
    plan = [
        ("protons", "%06i" % number, "%06i" % (number + 1000))
        for number in range(70)
    ]
    prepare_run(tmp_path, plan)
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda *args, **kwargs: None,
    )

    with caplog.at_level(logging.INFO, logger="atris_tools.run_chunks"):
        assert run_chunks(tmp_path) == 70

    records = [
        record
        for record in caplog.records
        if record.name == "atris_tools.run_chunks"
        and record.levelno == logging.INFO
    ]
    assert len(records) == 8


def test_run_chunks_stops_before_the_job_deadline(tmp_path, monkeypatch, caplog):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    with caplog.at_level(logging.INFO, logger="atris_tools.run_chunks"):
        assert run_chunks(
            tmp_path,
            deadline=1000,
            stop_before_end=100,
            clock=lambda: 900,
        ) == 0

    assert calls == []
    assert "wall-time safety window has begun" in caplog.text


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
                "mode": "response",
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


@pytest.mark.parametrize("value", ("response", "interface", "legacy-ascii"))
def test_output_modes_use_named_values(value):
    assert normalize_output_mode(value) == value


def test_output_mode_rejects_unknown_names():
    with pytest.raises(ValueError, match="response, interface, or legacy-ascii"):
        normalize_output_mode("unknown")


@pytest.mark.parametrize(
    ("mode", "value"),
    [
        ("response", "-1"),
        ("interface", "0"),
        ("legacy-ascii", "1"),
    ],
)
def test_run_chunks_translates_named_modes_for_atris(
    tmp_path, monkeypatch, mode, value
):
    prepare_run(tmp_path)
    calls = []
    monkeypatch.setattr(
        "atris_tools.run_chunks.subprocess.run",
        lambda command, **kwargs: calls.append(command),
    )

    assert run_chunks(tmp_path, mode=mode, entry=1) == 1
    assert calls[0][3] == value


def test_help_separates_atris_chunk_and_logging_options(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["atris-run", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "AtRIS execution options:" in help_text
    assert "Chunk plan and worker options:" in help_text
    assert "Logging options:" in help_text
    assert help_text.index("--physics-list") < help_text.index("--entry")
    assert help_text.index("--check-complete") < help_text.index("--quiet")
    assert "Examples:" in help_text
    normalized_help = " ".join(help_text.split())
    assert "atris-run runs/earth" in normalized_help
    assert "G4FORCENUMBEROFTHREADS=7" in normalized_help
    assert "--worker-index 2" in normalized_help
    assert "--worker-count 11" in normalized_help
    assert '"$JOB_END_TIME"' in normalized_help
    assert "--stop-before-end 1800" in normalized_help
    assert "--entry 17" in normalized_help
    assert "--check-complete" in normalized_help
