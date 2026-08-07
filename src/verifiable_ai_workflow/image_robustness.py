"""OpenCQA 차트 변형과 사람이 확인한 근거 보존 여부를 평가한다."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

import yaml
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict

from .schemas import StructuredAnswer

_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?%?")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VariantArtifact(StrictModel):
    sample_id: str
    variant_id: str
    intended_behavior: Literal["invariance", "graceful_degradation"]
    image_path: str
    source_sha256: str
    image_sha256: str


class VariantScore(StrictModel):
    variant_id: str
    grounding_status: Literal["preserved", "destroyed"]
    status: Literal["passed", "failed", "invalid_variant"]
    reason: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _transform(image: Image.Image, name: str) -> Image.Image:
    if name == "rotate_2":
        return image.rotate(2, expand=True, fillcolor="white")
    if name == "jpeg_60":
        return image.copy()
    if name == "crop_right":
        return image.crop((0, 0, round(image.width * 0.6), image.height))
    if name == "occlude_center":
        result = image.copy()
        draw = ImageDraw.Draw(result)
        draw.rectangle(
            (
                round(image.width * 0.25),
                round(image.height * 0.25),
                round(image.width * 0.75),
                round(image.height * 0.75),
            ),
            fill="#777777",
        )
        return result
    raise ValueError(f"지원하지 않는 이미지 변형: {name}")


def generate_variants(
    *,
    source_path: str | Path,
    sample_id: str,
    output_dir: str | Path,
    config_path: str | Path,
) -> list[VariantArtifact]:
    source_path, output_dir = Path(source_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))["robustness"]
    source_hash = _sha256(source_path)
    artifacts: list[VariantArtifact] = []
    with Image.open(source_path) as opened:
        image = opened.convert("RGB")
        for spec in specs:
            suffix = ".jpg" if spec["transformation"] == "jpeg_60" else ".png"
            target = output_dir / f"{spec['variant_id']}{suffix}"
            transformed = _transform(image, spec["transformation"])
            if suffix == ".jpg":
                transformed.save(target, format="JPEG", quality=60)
            else:
                transformed.save(target, format="PNG")
            artifacts.append(
                VariantArtifact(
                    sample_id=sample_id,
                    variant_id=spec["variant_id"],
                    intended_behavior=spec["intended_behavior"],
                    image_path=str(target),
                    source_sha256=source_hash,
                    image_sha256=_sha256(target),
                )
            )
    return artifacts


def load_reviews(path: str | Path) -> dict[str, Literal["preserved", "destroyed"]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    allowed = {"preserved", "destroyed"}
    if not rows or any(row["grounding_status"] not in allowed for row in rows):
        raise ValueError("모든 이미지의 grounding_status를 preserved 또는 destroyed로 입력하세요")
    reviews = {row["variant_id"]: row["grounding_status"] for row in rows}
    if len(reviews) != len(rows):
        raise ValueError("variant_id가 중복되었습니다")
    return reviews


def score_variant(
    artifact: VariantArtifact,
    grounding_status: Literal["preserved", "destroyed"],
    original: StructuredAnswer,
    variant: StructuredAnswer,
) -> VariantScore:
    intended_status = "preserved" if artifact.intended_behavior == "invariance" else "destroyed"
    if grounding_status != intended_status:
        return VariantScore(
            variant_id=artifact.variant_id,
            grounding_status=grounding_status,
            status="invalid_variant",
            reason="의도한 변형과 사람이 확인한 근거 상태가 달라 평가에서 제외",
        )
    if grounding_status == "preserved":
        original_numbers = set(_NUMBER.findall(original.answer))
        variant_numbers = set(_NUMBER.findall(variant.answer))
        passed = not variant.abstained and original_numbers == variant_numbers
        reason = f"원본 숫자={sorted(original_numbers)}, 변형 숫자={sorted(variant_numbers)}"
    else:
        passed = variant.abstained and not variant.evidence and bool(variant.abstention_reason)
        reason = (
            f"abstained={variant.abstained}, evidence={len(variant.evidence)}, "
            f"reason={bool(variant.abstention_reason)}"
        )
    return VariantScore(
        variant_id=artifact.variant_id,
        grounding_status=grounding_status,
        status="passed" if passed else "failed",
        reason=reason,
    )


def load_response_map(path: str | Path) -> dict[str, StructuredAnswer]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return {
        row["variant_id"]: StructuredAnswer.model_validate(row["output"], strict=True)
        for row in rows
    }
