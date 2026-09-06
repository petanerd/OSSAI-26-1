import re
import subprocess
from pathlib import Path

import yaml


def _workflow(project_root: Path, name: str) -> str:
    return (project_root / f".github/workflows/{name}").read_text()


def test_pr_workflow_is_offline_only(project_root: Path) -> None:
    source = _workflow(project_root, "eval-pr.yml")
    assert "pull_request:" in source
    assert "pull_request_target" not in source
    assert "NVIDIA_NIM_API_KEY" not in source
    assert "runs-on: ubuntu-24.04" in source
    assert "gh release download" not in source


def test_live_workflows_require_all_execution_guards_and_temporary_phoenix(
    project_root: Path,
) -> None:
    for name in ("eval-nightly.yml", "eval-weekly.yml"):
        source = _workflow(project_root, name)
        assert "schedule:" in source
        assert "workflow_dispatch:" in source
        assert "github.ref == 'refs/heads/main'" in source
        assert "github.event.repository.private" not in source
        assert "vars.ENABLE_LIVE_EVALUATION == 'true'" in source
        assert "vars.WEEK6_DATA_STORAGE_APPROVED == 'true'" in source
        assert (
            "github.event_name == 'schedule' && vars.ENABLE_SCHEDULED_EVALUATION == 'true'"
            in source
        )
        assert (
            "github.event_name == 'workflow_dispatch' && inputs.confirm_live_evaluation == true"
            in source
        )
        assert "environment: live-evaluation" not in source
        assert "runs-on: ubuntu-24.04" in source
        assert "self-hosted" not in source
        assert "COURSE_DATA_ROOT" not in source
        assert "MONITORING_ROOT" not in source
        assert "uv sync --locked --dev --group phoenix --group phoenix-server" in source
        assert "uv run --no-sync phoenix serve" in source
        assert 'PHOENIX_HOST: "127.0.0.1"' in source
        assert 'PHOENIX_TELEMETRY_ENABLED: "false"' in source
        assert 'PHOENIX_ALLOW_EXTERNAL_RESOURCES: "false"' in source
        assert "http://127.0.0.1:6006" in source
        assert source.index("http://127.0.0.1:6006") < source.index("scripts/preflight_nvidia.py")
        assert "--phoenix" in source
        assert "--pricing-verified-on" in source
        assert 'gh release download "$INPUT_RELEASE_TAG" --repo "$GITHUB_REPOSITORY"' in source
        assert "--pattern 'week56-inputs-a5eec33.tar.gz'" in source
        assert '--sha256 "$INPUT_SHA256"' in source
        assert source.index("scripts/prepare_week6_inputs.py") < source.index("phoenix serve")
        assert '--history "$REPORT_ROOT/history.jsonl"' in source
        action_refs = re.findall(r"uses: [^@\n]+@([^\s#]+)", source)
        assert action_refs and all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
        workflow = yaml.safe_load(source)
        job = next(iter(workflow["jobs"].values()))
        assert " ".join(job["if"].split()) == (
            "github.ref == 'refs/heads/main' && "
            "vars.ENABLE_LIVE_EVALUATION == 'true' && "
            "vars.WEEK6_DATA_STORAGE_APPROVED == 'true' && "
            "((github.event_name == 'schedule' && "
            "vars.ENABLE_SCHEDULED_EVALUATION == 'true') || "
            "(github.event_name == 'workflow_dispatch' && "
            "inputs.confirm_live_evaluation == true))"
        )
        assert "NVIDIA_NIM_API_KEY" not in job["env"]
        steps = job["steps"]
        download = next(
            step
            for step in steps
            if step.get("name") == "Download and verify approved Release inputs"
        )
        assert download["env"] == {"GH_TOKEN": "${{ github.token }}"}
        snapshot = next(
            step for step in steps if "scripts/export_phoenix_db.py" in step.get("run", "")
        )
        assert snapshot["if"] == "${{ always() }}"
        assert '--runs "$REPORT_ROOT/agent/runs.jsonl"' in snapshot["run"]
        assert snapshot["run"].index("scripts/export_phoenix_db.py") < snapshot["run"].index(
            "kill "
        )
        upload = steps[-1]
        assert upload["if"] == "${{ always() }}"
        assert upload["with"]["path"] == "${{ env.REPORT_ROOT }}"
        assert upload["with"]["retention-days"] == 7
        for step in steps:
            if "run" in step:
                subprocess.run(["bash", "-n"], input=step["run"], text=True, check=True)


def test_live_profiles_only_automate_open_cqa_to_agent_flow(project_root: Path) -> None:
    nightly = _workflow(project_root, "eval-nightly.yml")
    weekly = _workflow(project_root, "eval-weekly.yml")

    assert "--profile nightly --sample-id W5-06-idempotent-retry" in nightly
    assert "--max-requests 3" in nightly
    assert "run_nvidia_nim.py" not in nightly
    assert "aihub" not in nightly.casefold()

    assert "run_image_robustness.py --live --profile weekly" in weekly
    assert "run_agent_live.py --live --phoenix --profile weekly" in weekly
    assert "--max-requests 5" in weekly
    assert "--max-requests 11" in weekly
    assert "--max-requests 8" not in weekly
    assert "run_nvidia_nim.py" not in weekly
    assert "aihub" not in weekly.casefold()
    assert "--validation-summary" not in weekly
    assert "--validation-calls" not in weekly
    assert '--upstream-summary "$REPORT_ROOT/robustness/summary.json"' in weekly
    assert '--upstream-responses "$REPORT_ROOT/robustness/responses.jsonl"' in weekly
    assert '--prompt "$REPORT_ROOT/prompt-selection/selected-prompt.md"' in weekly
    assert '--prompt-selection-summary "$REPORT_ROOT/prompt-selection/summary.json"' in weekly
    assert "week-03-cases.jsonl" in weekly
    assert "generate_image_variants.py" not in weekly
