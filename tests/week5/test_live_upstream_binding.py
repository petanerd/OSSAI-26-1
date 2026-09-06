import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts import run_agent_live


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_valid_chain(root: Path) -> dict[str, Path]:
    source_git_sha = "a" * 40
    schema_sha256 = "b" * 64
    selection = root / "data/opencqa/week-03-selection.yaml"
    selection.parent.mkdir(parents=True)
    selection.write_text(
        """revision: 28db0fd26a12fd376f6c30b7feb8a4db32313424
license: GPL-3.0
source_split: val
course_splits:
  development: ["884"]
""",
        encoding="utf-8",
    )
    prompt = root / "runs/optimization/selected-prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("{question}\uc5d0 근거로 답하세요.\n", encoding="utf-8")
    output = {
        "answer": "47%",
        "evidence": [{"evidence_id": "chart", "quote": "47%", "page_number": 1}],
        "confidence": 1.0,
        "abstained": False,
        "abstention_reason": None,
        "tool_requests": [],
    }
    responses = root / "runs/robustness/responses.jsonl"
    responses.parent.mkdir(parents=True)
    responses.write_text(
        json.dumps(
            {
                "variant_id": "original",
                "raw_output": json.dumps(output, ensure_ascii=False),
                "output": output,
                "parse_error": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    source_summary = responses.parent / "summary.json"
    source_summary.write_text(
        json.dumps(
            {
                "status": "pass",
                "observed_status": "complete",
                "evidence_kind": "live_quality",
                "sample_id": "884",
                "family_id": "opencqa-val-884",
                "course_split": "development",
                "source_split": "val",
                "source_revision": "28db0fd26a12fd376f6c30b7feb8a4db32313424",
                "source_license": "GPL-3.0",
                "git_sha": source_git_sha,
                "schema_sha256": schema_sha256,
                "prompt_sha256": _sha256(prompt),
                "artifact_sha256": {"responses.jsonl": _sha256(responses)},
            }
        ),
        encoding="utf-8",
    )
    selection_summary = prompt.parent / "summary.json"
    selection_summary.write_text(
        json.dumps(
            {
                "status": "pass",
                "observed_status": "complete",
                "evidence_kind": "live_quality",
                "source_split": "val",
                "source_revision": "28db0fd26a12fd376f6c30b7feb8a4db32313424",
                "source_license": "GPL-3.0",
                "selected_prompt_sha256": _sha256(prompt),
                "artifact_sha256": {"selected-prompt.md": _sha256(prompt)},
            }
        ),
        encoding="utf-8",
    )
    evaluation = responses.parent / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            [
                {
                    "variant_id": "original",
                    "grounding_status": "preserved",
                    "status": "failed",
                    "reason": "원본 점수=0.139, evidence=1",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    evaluation_manifest = responses.parent / "evaluation-manifest.json"
    evaluation_manifest.write_text(
        json.dumps(
            {
                "source_git_sha": source_git_sha,
                "evaluation_sha256": _sha256(evaluation),
                "responses_sha256": _sha256(responses),
                "schema_sha256": schema_sha256,
                "scorer_sha256": "c" * 64,
                "metric_sha256": "d" * 64,
            }
        ),
        encoding="utf-8",
    )
    return {
        "source_summary": source_summary,
        "responses": responses,
        "selection_summary": selection_summary,
        "prompt": prompt,
        "evaluation": evaluation,
        "evaluation_manifest": evaluation_manifest,
    }


def _load(paths: dict[str, Path], root: Path):
    return run_agent_live._load_upstream_context(
        paths["source_summary"],
        paths["responses"],
        paths["selection_summary"],
        paths["prompt"],
        project_root=root,
    )


def test_loader_accepts_bound_week4_artifacts(tmp_path: Path) -> None:
    paths = _write_valid_chain(tmp_path)

    context = _load(paths, tmp_path)

    assert context.sample_id == "884"
    assert context.family_id == "opencqa-val-884"
    assert context.source_evidence_kind == "live_quality"
    assert context.selected_prompt_sha256 == _sha256(paths["prompt"])
    assert context.responses_sha256 == _sha256(paths["responses"])
    assert context.output.answer == "47%"

    quality = run_agent_live._load_upstream_answer_quality(
        paths["evaluation"],
        paths["source_summary"],
        paths["responses"],
        project_root=tmp_path,
    )
    assert quality == {
        "status": "fail",
        "reason": "원본 점수=0.139, evidence=1",
    }


def test_loader_rejects_response_hash_mismatch(tmp_path: Path) -> None:
    paths = _write_valid_chain(tmp_path)
    paths["responses"].write_text("{}\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="responses.jsonl SHA-256"):
        _load(paths, tmp_path)


@pytest.mark.parametrize("status", ["fail", "inconclusive"])
def test_loader_rejects_nonpassing_upstream_before_live_call(
    tmp_path: Path,
    status: str,
) -> None:
    paths = _write_valid_chain(tmp_path)
    summary = json.loads(paths["source_summary"].read_text(encoding="utf-8"))
    summary["status"] = status
    paths["source_summary"].write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(SystemExit, match="구조 수집을 통과한 live_quality"):
        _load(paths, tmp_path)


def test_loader_rejects_path_outside_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paths = _write_valid_chain(root)
    outside = tmp_path / "outside-summary.json"
    outside.write_text(paths["source_summary"].read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(SystemExit, match="프로젝트 안의 실제 파일"):
        run_agent_live._load_upstream_context(
            outside,
            paths["responses"],
            paths["selection_summary"],
            paths["prompt"],
            project_root=root,
        )


def test_main_rejects_prompt_mismatch_before_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _write_valid_chain(tmp_path)
    paths["prompt"].write_text("바뀐 지시문\n", encoding="utf-8")
    provider_called = False

    def unexpected_provider(*args, **kwargs):
        nonlocal provider_called
        provider_called = True
        raise AssertionError("상류 검증 실패 후 provider를 생성하면 안 됩니다")

    monkeypatch.setattr(run_agent_live, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(run_agent_live, "build_course_provider", unexpected_provider)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_live.py",
            "--live",
            "--phoenix",
            "--profile",
            "week5",
            "--upstream-summary",
            str(paths["source_summary"]),
            "--upstream-responses",
            str(paths["responses"]),
            "--upstream-evaluation",
            str(paths["evaluation"]),
            "--prompt-selection-summary",
            str(paths["selection_summary"]),
            "--selected-prompt",
            str(paths["prompt"]),
            "--max-requests",
            "11",
            "--max-input-tokens",
            "220000",
            "--max-output-tokens",
            "5500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "1800",
            "--catalog-verified-on",
            "2026-08-31",
            "--pricing-verified-on",
            "2026-08-31",
            "--output",
            str(tmp_path / "output"),
        ],
    )

    with pytest.raises(SystemExit, match="선택 지시문 SHA-256"):
        run_agent_live.main()
    assert provider_called is False


def test_main_rejects_tampered_evaluation_manifest_before_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _write_valid_chain(tmp_path)
    manifest = json.loads(paths["evaluation_manifest"].read_text(encoding="utf-8"))
    manifest["evaluation_sha256"] = "0" * 64
    paths["evaluation_manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    provider_called = False

    def unexpected_provider(*args, **kwargs):
        nonlocal provider_called
        provider_called = True
        raise AssertionError("상류 품질 계보 실패 후 provider를 생성하면 안 됩니다")

    monkeypatch.setattr(run_agent_live, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(run_agent_live, "build_course_provider", unexpected_provider)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_live.py",
            "--live",
            "--phoenix",
            "--profile",
            "week5",
            "--upstream-summary",
            str(paths["source_summary"]),
            "--upstream-responses",
            str(paths["responses"]),
            "--upstream-evaluation",
            str(paths["evaluation"]),
            "--prompt-selection-summary",
            str(paths["selection_summary"]),
            "--selected-prompt",
            str(paths["prompt"]),
            "--max-requests",
            "11",
            "--max-input-tokens",
            "220000",
            "--max-output-tokens",
            "5500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "1800",
            "--catalog-verified-on",
            "2026-08-31",
            "--pricing-verified-on",
            "2026-08-31",
            "--output",
            str(tmp_path / "output"),
        ],
    )

    with pytest.raises(SystemExit, match="품질 평가 계보"):
        run_agent_live.main()
    assert provider_called is False


def test_main_requires_phoenix_before_loading_upstream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    upstream_called = False

    def unexpected_upstream(*args, **kwargs):
        nonlocal upstream_called
        upstream_called = True
        raise AssertionError("Phoenix 없는 live 실행은 상류 파일을 읽으면 안 됩니다")

    monkeypatch.setattr(run_agent_live, "_load_upstream_context", unexpected_upstream)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_live.py",
            "--live",
            "--profile",
            "week5",
            "--upstream-summary",
            "summary.json",
            "--upstream-responses",
            "responses.jsonl",
            "--upstream-evaluation",
            "evaluation.json",
            "--prompt-selection-summary",
            "selection.json",
            "--selected-prompt",
            "prompt.md",
            "--max-requests",
            "11",
            "--max-input-tokens",
            "220000",
            "--max-output-tokens",
            "5500",
            "--max-cost-usd",
            "0.01",
            "--max-wall-seconds",
            "1800",
            "--catalog-verified-on",
            "2026-08-31",
            "--pricing-verified-on",
            "2026-08-31",
            "--output",
            str(tmp_path / "output"),
        ],
    )

    with pytest.raises(SystemExit, match="Phoenix"):
        run_agent_live.main()
    assert upstream_called is False
