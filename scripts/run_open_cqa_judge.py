"""OpenCQA 답 두 개를 A/B·B/A 순서로 두 번 비교한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

import yaml

from verifiable_ai_workflow.config.secrets import load_project_env
from verifiable_ai_workflow.judge_calibration import load_pairs
from verifiable_ai_workflow.judge_metrics import build_arena_metric, measure
from verifiable_ai_workflow.judge_model import CourseJudgeModel
from verifiable_ai_workflow.providers.litellm_provider import LiteLLMProvider

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "configs/week-03-judge.yaml"
PAIRS = PROJECT_ROOT / "local-data/opencqa/week-03-pairs.jsonl"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_state() -> tuple[str, bool]:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return sha, dirty


def required_requests(pair_count: int) -> int:
    return pair_count * 2 * 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-judge", action="store_true")
    parser.add_argument("--pair-limit", type=int, default=5)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--catalog-verified-on", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live_judge:
        raise SystemExit("실제 Judge 호출에는 --live-judge가 필요합니다")
    if args.catalog_verified_on > date.today():
        raise SystemExit("--catalog-verified-on은 미래 날짜일 수 없습니다")

    pairs = load_pairs(PAIRS)
    if not 1 <= args.pair_limit <= len(pairs):
        raise SystemExit(f"--pair-limit는 1부터 {len(pairs)}까지입니다")
    pairs = pairs[: args.pair_limit]
    minimum = required_requests(len(pairs))
    if args.max_requests < minimum:
        raise SystemExit(f"{len(pairs)}쌍을 두 번·양방향 비교하려면 최소 {minimum}회가 필요합니다")

    git_sha, git_dirty = _git_state()
    if len(pairs) > 5 and git_dirty:
        raise SystemExit("30쌍 품질 실행은 변경사항이 없는 Git commit에서만 허용합니다")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    settings = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    provider_settings = settings["provider"]
    rubric = PROJECT_ROOT / settings["rubric"]
    load_project_env(PROJECT_ROOT)
    calls_path = args.output / "judge-calls.jsonl"

    def record_call(call: dict) -> None:
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")

    request_input = provider_settings["request_input_token_ceiling"]
    request_output = provider_settings["request_output_token_ceiling"]
    request_cost = provider_settings["request_cost_ceiling_usd"]
    provider = LiteLLMProvider(
        model=provider_settings["model"],
        expected_actual_model=provider_settings["expected_actual_model"],
        api_key_env=provider_settings["api_key_env"],
        api_base=provider_settings["api_base"],
        structured_output="json_schema",
        max_requests=args.max_requests,
        requests_per_minute=provider_settings["requests_per_minute"],
        max_retries=0,
        retry_initial_seconds=1,
        max_cost_usd=args.max_cost_usd,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_wall_seconds=args.max_wall_seconds,
        request_input_token_ceiling=request_input,
        request_output_token_ceiling=request_output,
        input_cost_per_token_usd=request_cost / request_input,
        output_cost_per_token_usd=0.0,
        on_response_received=record_call,
    )
    model = CourseJudgeModel(provider)
    metric = build_arena_metric(model, rubric)
    results_path = args.output / "judge-results.jsonl"
    result_count = 0
    for pair in pairs:
        for trial in (1, 2):
            model.call_id = f"{pair.pair_id}/trial-{trial}/ab"
            winner_ab = measure(metric, pair)
            model.call_id = f"{pair.pair_id}/trial-{trial}/ba"
            winner_ba = measure(metric, pair, reverse=True)
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "pair_id": pair.pair_id,
                            "trial": trial,
                            "winner_ab": winner_ab,
                            "winner_ba": winner_ba,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            result_count += 1

    summary = {
        "status": "completed",
        "evidence_kind": "exploratory" if len(pairs) <= 5 else "live_quality",
        "pair_count": len(pairs),
        "trial_count": result_count,
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "model": provider.model,
        "expected_actual_model": provider.expected_actual_model,
        "catalog_verified_on": args.catalog_verified_on.isoformat(),
        "pairs_sha256": _sha256(PAIRS),
        "rubric_sha256": _sha256(rubric),
        "budget": provider.budget.summary(),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OpenCQA {len(pairs)}쌍 × 2회 × A/B·B/A 비교를 완료했습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
