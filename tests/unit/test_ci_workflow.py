import re
from pathlib import Path

import yaml


def test_public_ci_only_runs_offline_checks(project_root: Path) -> None:
    source = (project_root / ".github/workflows/eval-pr.yml").read_text()
    workflow = yaml.safe_load(source)
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["test-only"]
    assert job["runs-on"] == "ubuntu-24.04"
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert commands == [
        'python -m pip install --disable-pip-version-check --no-deps "uv==0.11.28"',
        "uv sync --locked --dev",
        "uv run --no-sync ruff check .",
        "uv run --no-sync pytest",
        "uv run --no-sync python scripts/inspect_deterministic_scoring_case.py",
    ]
    assert all(term not in source for term in ("secrets.", "--live", "pull_request_target"))
    action_refs = re.findall(r"uses: [^@\n]+@([^\s#]+)", source)
    assert action_refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
