"""합성 입력 묶음의 안전한 추출과 열린 SQLite WAL의 백업을 확인한다."""

import hashlib
import io
import os
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import closing
from pathlib import Path

import pytest
import yaml

from scripts.export_phoenix_db import export_database
from scripts.prepare_week6_inputs import INPUT_FILES, prepare_inputs

EXPECTED_FILES = (
    "local-data/opencqa/week-03-cases.jsonl",
    "local-data/opencqa/images/884.jpg",
    "local-data/opencqa/week-04-variants/case.json",
    "local-data/opencqa/week-04-variants/variants.jsonl",
    "local-data/opencqa/week-04-variants/variant-review.csv",
    "local-data/opencqa/week-04-variants/rotate-2.png",
    "local-data/opencqa/week-04-variants/jpeg-60.jpg",
    "local-data/opencqa/week-04-variants/crop-left.png",
    "local-data/opencqa/week-04-variants/occlude-answer.png",
    "local-data/week-04-full-runs/optimization-4b53815/summary.json",
    "local-data/week-04-full-runs/optimization-4b53815/selected-prompt.md",
    "local-data/week-04-full-runs/optimization-4b53815/calls.jsonl",
    "local-data/week-04-full-runs/optimization-4b53815/validation.jsonl",
    "local-data/week-04-full-runs/robustness-4b53815/summary.json",
    "local-data/week-04-full-runs/robustness-4b53815/responses.jsonl",
    "local-data/week-04-full-runs/robustness-4b53815/evaluation.json",
    "local-data/week-04-full-runs/robustness-4b53815/evaluation-manifest.json",
)
PAYLOAD = b"test_only synthetic input\n"


def _archive(tmp_path: Path, defect: str = "") -> tuple[Path, str]:
    members = [tarfile.TarInfo(name) for name in EXPECTED_FILES]
    if defect == "extra":
        members.append(tarfile.TarInfo("local-data/unapproved.txt"))
    elif defect == "missing":
        members.pop()
    elif defect == "duplicate":
        members.append(tarfile.TarInfo(EXPECTED_FILES[0]))
    elif defect == "relative_escape":
        members[0].name = "../escaped.txt"
    elif defect == "absolute_escape":
        members[0].name = str(tmp_path / "escaped.txt")
    elif defect in {"symlink", "hardlink", "directory"}:
        members[0].type = {
            "symlink": tarfile.SYMTYPE,
            "hardlink": tarfile.LNKTYPE,
            "directory": tarfile.DIRTYPE,
        }[defect]
        members[0].linkname = "../../escaped.txt"
    archive = tmp_path / "inputs.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for member in members:
            member.size = len(PAYLOAD) if member.isfile() else 0
            handle.addfile(member, io.BytesIO(PAYLOAD) if member.isfile() else None)
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_release_inputs_extract_only_the_fixed_17_files(tmp_path: Path) -> None:
    assert len(EXPECTED_FILES) == 17
    assert INPUT_FILES == frozenset(EXPECTED_FILES)
    archive, digest = _archive(tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    prepare_inputs(archive, digest, checkout)

    extracted = {
        path.relative_to(checkout).as_posix() for path in checkout.rglob("*") if path.is_file()
    }
    assert extracted == set(EXPECTED_FILES)
    assert all((checkout / name).read_bytes() == PAYLOAD for name in EXPECTED_FILES)
    assert not any(path.is_symlink() for path in checkout.rglob("*"))


@pytest.mark.parametrize(
    ("profile", "step_name", "expected_reports"),
    [
        (
            "nightly", "Prepare Week 4 answers for nightly",
            {
                "prompt-selection/summary.json", "prompt-selection/selected-prompt.md",
                "robustness/summary.json", "robustness/responses.jsonl",
            },
        ),
        (
            "weekly", "Prepare Week 4 selection for weekly",
            {
                "prompt-selection/summary.json", "prompt-selection/selected-prompt.md",
                "prompt-selection/calls.jsonl", "prompt-selection/validation.jsonl",
            },
        ),
    ],
)
def test_workflow_prepares_reports_from_verified_release_inputs(
    tmp_path: Path, project_root: Path, profile: str, step_name: str, expected_reports: set[str],
) -> None:
    archive, digest = _archive(tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    prepare_inputs(archive, digest, checkout)
    workflow = yaml.safe_load(
        (project_root / f".github/workflows/eval-{profile}.yml").read_text()
    )
    step = next(
        step for job in workflow["jobs"].values() for step in job["steps"]
        if step.get("name") == step_name
    )
    report_root = "reports/test-only"

    subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=checkout,
        env={"PATH": os.environ["PATH"], "REPORT_ROOT": report_root},
        check=True,
        timeout=10,
    )

    reports = checkout / report_root
    assert {
        path.relative_to(reports).as_posix() for path in reports.rglob("*") if path.is_file()
    } == expected_reports
    assert all((reports / name).read_bytes() == PAYLOAD for name in expected_reports)


@pytest.mark.parametrize(
    "defect",
    [
        "sha256", "extra", "missing", "duplicate", "relative_escape", "absolute_escape",
        "symlink", "hardlink", "directory",
    ],
)
def test_release_inputs_reject_unapproved_archive_before_extraction(
    tmp_path: Path, defect: str,
) -> None:
    archive, digest = _archive(tmp_path, defect)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    if defect == "sha256":
        digest = ("0" if digest[0] != "0" else "1") + digest[1:]

    with pytest.raises(ValueError):
        prepare_inputs(archive, digest, checkout)

    assert list(checkout.iterdir()) == []
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize("obstacle", ["file", "symlink", "parent_symlink", "parent_file"])
def test_release_inputs_do_not_overwrite_or_follow_existing_paths(
    tmp_path: Path, obstacle: str,
) -> None:
    archive, digest = _archive(tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "existing.txt"
    sentinel.write_bytes(b"keep existing data")
    target = checkout / EXPECTED_FILES[-1]
    if obstacle == "parent_symlink":
        (checkout / "local-data").symlink_to(outside, target_is_directory=True)
    elif obstacle == "parent_file":
        (checkout / "local-data").write_bytes(b"keep existing data")
    else:
        target.parent.mkdir(parents=True)
        if obstacle == "symlink":
            target.symlink_to(sentinel)
        else:
            target.write_bytes(b"keep existing data")

    with pytest.raises(ValueError):
        prepare_inputs(archive, digest, checkout)

    assert sentinel.read_bytes() == b"keep existing data"
    assert list(outside.iterdir()) == [sentinel]
    assert not (checkout / EXPECTED_FILES[0]).exists()
    if obstacle in {"file", "symlink"}:
        assert target.read_bytes() == b"keep existing data"
    elif obstacle == "parent_file":
        assert (checkout / "local-data").read_bytes() == b"keep existing data"


def test_phoenix_backup_preserves_committed_wal_rows_while_source_is_open(tmp_path: Path) -> None:
    source = tmp_path / "phoenix.db"
    output = tmp_path / "download" / "phoenix.db"
    with closing(sqlite3.connect(source)) as active:
        assert active.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        active.execute("CREATE TABLE traces (id TEXT PRIMARY KEY)")
        active.execute("INSERT INTO traces VALUES ('synthetic-trace-01')")
        active.commit()
        assert source.with_name("phoenix.db-wal").stat().st_size > 0

        export_database(source, output)

        with closing(sqlite3.connect(output)) as restored:
            assert restored.execute("PRAGMA quick_check").fetchone() == ("ok",)
            assert restored.execute("SELECT id FROM traces").fetchall() == [("synthetic-trace-01",)]
        assert active.execute("SELECT COUNT(*) FROM traces").fetchone() == (1,)


def test_phoenix_backup_never_overwrites_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "phoenix.db"
    with closing(sqlite3.connect(source)) as active:
        active.execute("CREATE TABLE traces (id TEXT)")
        active.commit()
    output = tmp_path / "existing.db"
    output.write_bytes(b"keep existing database")

    with pytest.raises(FileExistsError):
        export_database(source, output)

    assert output.read_bytes() == b"keep existing database"


def test_phoenix_backup_preserves_database_but_fails_for_truncated_jsonl(
    tmp_path: Path, project_root: Path,
) -> None:
    source = tmp_path / "phoenix.db"
    output = tmp_path / "download" / "phoenix.db"
    runs = tmp_path / "runs.jsonl"
    runs.write_text('{"phoenix_trace_id":', encoding="utf-8")
    with closing(sqlite3.connect(source)) as active:
        active.execute("CREATE TABLE traces (id TEXT)")
        active.execute("INSERT INTO traces VALUES ('synthetic-trace-01')")
        active.commit()
    original_bytes = source.read_bytes()

    result = subprocess.run(
        [
            sys.executable, "-X", "utf8", str(project_root / "scripts/export_phoenix_db.py"),
            "--source", str(source), "--output", str(output), "--runs", str(runs),
        ],
        capture_output=True, text=True, encoding="utf-8", timeout=10,
    )

    assert result.returncode != 0
    assert "DB 사본은 저장했지만 Agent JSONL을 읽거나 해석하지 못했습니다" in result.stderr
    assert "복사·무결성 확인 완료" not in result.stdout
    assert source.read_bytes() == original_bytes
    with closing(sqlite3.connect(output)) as restored:
        assert restored.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert restored.execute("SELECT id FROM traces").fetchall() == [("synthetic-trace-01",)]


@pytest.mark.parametrize("agent_arrives", [True, False], ids=["delayed-agent", "missing-agent"])
def test_phoenix_backup_waits_for_jsonl_agent_and_preserves_missing_trace_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent_arrives: bool,
) -> None:
    source = tmp_path / "phoenix.db"
    output = tmp_path / "download" / "phoenix.db"
    runs = tmp_path / "runs.jsonl"
    runs.write_text('{"phoenix_trace_id": "expected-trace"}\n')
    waits: list[float] = []
    with closing(sqlite3.connect(source)) as active:
        active.execute("PRAGMA journal_mode=WAL")
        active.execute("CREATE TABLE traces (id INTEGER PRIMARY KEY, trace_id TEXT)")
        active.execute("CREATE TABLE spans (trace_rowid INTEGER, span_kind TEXT)")
        active.executemany(
            "INSERT INTO traces VALUES (?, ?)", [(1, "expected-trace"), (2, "unrelated-trace")]
        )
        active.executemany("INSERT INTO spans VALUES (?, ?)", [(1, "LLM"), (2, "AGENT")])
        active.commit()

        def record_agent_instead_of_sleep(seconds: float) -> None:
            waits.append(seconds)
            if agent_arrives and len(waits) == 1:
                active.execute("INSERT INTO spans VALUES (1, 'AGENT')")
                active.commit()

        monkeypatch.setattr("scripts.export_phoenix_db.time.sleep", record_agent_instead_of_sleep)
        if agent_arrives:
            export_database(source, output, runs)
        else:
            with pytest.raises(ValueError, match="Agent 기록 1개"):
                export_database(source, output, runs)

        assert waits == [0.1] * (1 if agent_arrives else 50)
        with closing(sqlite3.connect(output)) as restored:
            assert restored.execute("PRAGMA quick_check").fetchone() == ("ok",)
            assert restored.execute("SELECT COUNT(*) FROM traces").fetchone() == (2,)
            assert restored.execute(
                "SELECT span_kind FROM spans WHERE trace_rowid = 1 ORDER BY span_kind"
            ).fetchall() == ([("AGENT",), ("LLM",)] if agent_arrives else [("LLM",)])
