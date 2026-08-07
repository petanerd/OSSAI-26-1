from verifiable_ai_workflow.config.settings import load_settings
from verifiable_ai_workflow.course_live import build_course_provider
from verifiable_ai_workflow.live_execution import LiveBudgetCaps


def test_course_provider_reuses_caps_and_model(monkeypatch, project_root) -> None:
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "test-key")
    settings = load_settings(project_root / "configs/nvidia-nim-gemma4.yaml")
    caps = LiveBudgetCaps(
        max_requests=2,
        max_attempts=2,
        max_input_tokens=40000,
        max_output_tokens=1000,
        max_cost_usd=0.01,
        max_wall_seconds=240,
    )

    provider = build_course_provider(settings, caps)

    assert provider.model == "nvidia_nim/google/gemma-4-31b-it"
    assert provider.budget.state.caps == caps
    assert provider.structured_output == "json_schema"
