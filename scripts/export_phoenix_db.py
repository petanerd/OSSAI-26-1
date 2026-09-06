"""Phoenix SQLite를 WAL까지 포함한 단일 DB 복사본으로 저장한다."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def export_database(source: Path, output: Path, runs: Path | None = None) -> None:
    source = source.resolve(strict=True)
    runs_error: Exception | None = None
    try:
        expected = (
            {
                json.loads(line)["phoenix_trace_id"]
                for line in runs.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
            if runs is not None and runs.is_file()
            else set()
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        expected = set()
        runs_error = exc
    missing = expected
    output.parent.mkdir(parents=True, exist_ok=True)
    # 기존 결과 파일을 덮어쓰지 않는다. 실행 중인 DB의 단순 파일 복사는 쓰지 않는다.
    with output.open("xb"):
        pass
    try:
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original,
            closing(sqlite3.connect(output)) as copy,
        ):
            # HTTP 수신 직후에는 DB 기록이 끝나지 않을 수 있다.
            # 자식 단계 뒤에 전송되는 마지막 AGENT 단계의 저장을 최대 5초 기다린다.
            if expected:
                for _attempt in range(50):
                    saved = {
                        row[0]
                        for row in original.execute(
                            "SELECT traces.trace_id FROM traces JOIN spans "
                            "ON spans.trace_rowid = traces.id WHERE spans.span_kind = 'AGENT'"
                        )
                    }
                    missing = expected - saved
                    if not missing:
                        break
                    time.sleep(0.1)
            original.backup(copy)
            if copy.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Phoenix DB 복사본 검사에 실패했습니다")
    except Exception:
        output.unlink()  # 이 함수가 방금 만든 불완전한 복사본만 제거한다.
        raise
    if runs_error is not None:
        raise ValueError(
            "DB 사본은 저장했지만 Agent JSONL을 읽거나 해석하지 못했습니다"
        ) from runs_error
    if missing:
        # 진단용 DB는 보존하지만 기록 누락을 성공으로 표시하지 않는다.
        raise ValueError(f"DB 사본은 저장했지만 JSONL의 Agent 기록 {len(missing)}개가 없습니다")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--runs", type=Path, help="대조할 agent/runs.jsonl; 실행 전 중단이면 없을 수 있음"
    )
    args = parser.parse_args()
    export_database(args.source, args.output, args.runs)
    print(f"Phoenix DB 복사·무결성 확인 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
