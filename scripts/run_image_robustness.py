"""OpenCQA 원본과 변형 이미지 4개를 같은 VLM prompt로 실행한다."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path

from deepeval.prompt import Prompt

from verifiable_ai_workflow.config.secrets import load_project_env
from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.course_live import build_course_provider
from verifiable_ai_workflow.image_robustness import VariantArtifact, load_reviews
from verifiable_ai_workflow.live_execution import LiveBudgetCaps
from verifiable_ai_workflow.schemas import StructuredAnswer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VARIANT_ROOT = PROJECT_ROOT / "local-data/opencqa/week-04-variants"


def _git_sha() -> str:
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise SystemExit("이미지 견고성 실제 실행은 변경사항이 없는 Git commit에서만 허용합니다")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _image_message(path: Path, question: str) -> dict:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = "jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "png"
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": question},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{suffix};base64,{encoded}"},
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--prompt", type=Path, default=PROJECT_ROOT / "prompts/week-04-baseline.md")
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument("--max-cost-usd", type=float, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("실제 VLM 호출에는 --live가 필요합니다")
    if args.max_requests != 5:
        raise SystemExit("원본 1개와 변형 4개 실행에는 --max-requests 5가 필요합니다")
    git_sha = _git_sha()
    load_reviews(VARIANT_ROOT / "variant-review.csv")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"비어 있지 않은 출력 폴더입니다: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)

    case = json.loads((VARIANT_ROOT / "case.json").read_text(encoding="utf-8"))
    variants = [
        VariantArtifact.model_validate_json(line)
        for line in (VARIANT_ROOT / "variants.jsonl").read_text().splitlines()
        if line.strip()
    ]
    images = [("original", PROJECT_ROOT / case["original_image"])] + [
        (item.variant_id, Path(item.image_path)) for item in variants
    ]
    prompt = Prompt(text_template=args.prompt.read_text(encoding="utf-8"))
    instruction = prompt.interpolate(question=case["question"])
    caps = LiveBudgetCaps(
        max_requests=5,
        max_attempts=5,
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_cost_usd=args.max_cost_usd,
        max_wall_seconds=args.max_wall_seconds,
    )
    settings = load_settings(PROJECT_ROOT / "configs/nvidia-nim-gemma4.yaml")
    load_project_env(PROJECT_ROOT)
    calls_path = args.output / "calls.jsonl"

    def record_call(call: dict) -> None:
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")

    provider = build_course_provider(settings, caps, on_response=record_call)
    responses_path = args.output / "responses.jsonl"
    for variant_id, image_path in images:
        raw = provider.generate(
            f"{case['sample_id']}:{variant_id}",
            [
                {"role": "system", "content": instruction},
                _image_message(image_path, case["question"]),
            ],
        )
        parsed = StructuredAnswer.model_validate_json(raw)
        with responses_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"variant_id": variant_id, "output": parsed.model_dump(mode="json")},
                    ensure_ascii=False,
                )
                + "\n"
            )
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "evidence_kind": "live_quality",
                "git_sha": git_sha,
                "sample_id": case["sample_id"],
                "record_count": 5,
                "budget": provider.budget.summary(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("원본 1개와 변형 4개의 VLM 응답을 저장했습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
