"""승인된 Week 5·6 입력 묶음의 해시·파일 범위를 확인한 뒤 checkout 안에 푼다."""

from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 64 * 1024 * 1024
INPUT_FILES = frozenset(
    [
        "local-data/opencqa/week-03-cases.jsonl",
        "local-data/opencqa/images/884.jpg",
        *(
            f"local-data/opencqa/week-04-variants/{name}"
            for name in (
                "case.json",
                "variants.jsonl",
                "variant-review.csv",
                "rotate-2.png",
                "jpeg-60.jpg",
                "crop-left.png",
                "occlude-answer.png",
            )
        ),
        *(
            f"local-data/week-04-full-runs/optimization-4b53815/{name}"
            for name in ("summary.json", "selected-prompt.md", "calls.jsonl", "validation.jsonl")
        ),
        *(
            f"local-data/week-04-full-runs/robustness-4b53815/{name}"
            for name in (
                "summary.json",
                "responses.jsonl",
                "evaluation.json",
                "evaluation-manifest.json",
            )
        ),
    ]
)


def prepare_inputs(archive: Path, expected_sha256: str, project_root: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("승인된 입력 묶음의 소문자 SHA-256 64자리가 필요합니다")
    if not archive.is_file() or archive.stat().st_size > MAX_BYTES:
        raise ValueError("입력 묶음이 없거나 64 MiB를 초과했습니다")
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != expected_sha256:
        raise ValueError("입력 묶음 SHA-256이 승인값과 다릅니다")

    root = project_root.resolve(strict=True)
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        if len(members) != len(INPUT_FILES) or {item.name for item in members} != INPUT_FILES:
            raise ValueError("입력 묶음은 정해진 17개 파일만 포함해야 합니다")
        if any(not item.isfile() or item.size < 0 for item in members):
            raise ValueError("링크·폴더·특수 파일은 입력으로 허용하지 않습니다")
        if sum(item.size for item in members) > MAX_BYTES:
            raise ValueError("압축을 푼 입력이 64 MiB를 초과합니다")
        for item in members:
            target = root / item.name
            if target.exists() or target.is_symlink():
                raise ValueError(f"기존 입력을 덮어쓰지 않습니다: {item.name}")
            for parent in target.parents:
                if parent == root:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise ValueError(f"안전하지 않은 입력 경로입니다: {item.name}")
        # 승인된 고정 파일만 추출하며 tar의 링크·경로 보호도 함께 적용한다.
        handle.extractall(root, members=members, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    prepare_inputs(args.archive, args.sha256, PROJECT_ROOT)
    print("입력 17파일의 묶음 해시·경로 확인 완료 (모델 API 호출 없음)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
