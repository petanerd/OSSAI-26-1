import re
from pathlib import Path


def test_pr_workflow_is_offline_only(project_root: Path) -> None:
    source = (project_root / ".github/workflows/eval-pr.yml").read_text()
    assert "pull_request:" in source
    assert "pull_request_target" not in source
    assert "NVIDIA_NIM_API_KEY" not in source
    assert "run_agent_cases.py" in source


def test_live_workflows_are_guarded_and_pinned(project_root: Path) -> None:
    for name in ("eval-nightly.yml", "eval-weekly.yml"):
        source = (project_root / f".github/workflows/{name}").read_text()
        assert "self-hosted" in source
        assert "LIVE_TASK_ENABLED" in source
        assert "environment: live-evaluation" in source
        assert "preflight_nvidia.py" in source
        action_refs = re.findall(r"uses: [^@\n]+@([^\s#]+)", source)
        assert action_refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)


def test_scheduled_sample_counts_match_the_course_contract(project_root: Path) -> None:
    nightly = (project_root / ".github/workflows/eval-nightly.yml").read_text()
    weekly = (project_root / ".github/workflows/eval-weekly.yml").read_text()
    assert "--limit 3" in nightly
    assert "--split validation" in weekly
    assert "--max-requests 8" in weekly
    assert "--max-requests 5" in weekly
