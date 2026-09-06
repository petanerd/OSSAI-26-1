import io
import json
from http.client import IncompleteRead
from urllib.parse import parse_qs, urlparse

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from scripts.run_agent_live import _RunTracer
from verifiable_ai_workflow import agent_lab


@pytest.fixture
def stored_agent_run(project_root):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    runs, _ = agent_lab.run_cases(
        agent_lab.load_agent_cases(project_root / "data/agent/week-05-cases.yaml"),
        agent_lab.RecordedAgentProvider(project_root / "data/recorded/week-05-agent-turns.jsonl"),
        upstream_context=agent_lab.load_agent_upstream_context(
            project_root / "data/recorded/week-05-upstream.json"
        ),
        prompt="test",
        records=agent_lab.load_lookup_records(project_root / "data/agent/week-05-lookup.yaml"),
        tracer=_RunTracer(provider.get_tracer(__name__), run_id="test-only", trial_id="t01"),
    )
    spans = [
        {
            "context": {
                "trace_id": f"{span.context.trace_id:032x}",
                "span_id": f"{span.context.span_id:016x}",
            },
            "span_kind": span.attributes["openinference.span.kind"],
            "parent_id": f"{span.parent.span_id:016x}" if span.parent else None,
            "attributes": dict(span.attributes),
        }
        for span in exporter.get_finished_spans()
    ]
    provider.shutdown()
    return runs, spans


@pytest.mark.parametrize(
    "fault", [None, "llm_missing", "root_missing", "wrong_parent", "wrong_run", "duplicate_id",
              "http_error", "incomplete_read", "bad_json", "pagination", "export_failure"]
)
def test_storage_check_requires_complete_persisted_tree(monkeypatch, stored_agent_run, fault):
    runs, spans = stored_agent_run
    assert len(spans) == 22
    expected = {run.sample_id: run.phoenix_trace_id for run in runs}
    if fault == "llm_missing":
        spans.remove(next(span for span in spans if span["span_kind"] == "LLM"))
    elif fault == "root_missing":
        spans.remove(next(span for span in spans if span["span_kind"] == "AGENT"))
    elif fault == "wrong_parent":
        spans[0]["parent_id"] = "0" * 16
    elif fault == "wrong_run":
        spans[0]["attributes"]["course.run_id"] = "other-run"
    elif fault == "duplicate_id":
        spans[0]["context"]["span_id"] = spans[1]["context"]["span_id"]
    elif fault == "export_failure":
        class RejectingExporter(InMemorySpanExporter):
            def export(self, spans):
                return SpanExportResult.FAILURE

        exporter = RejectingExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        with provider.get_tracer(__name__).start_as_current_span("agent.run") as span:
            assert span.get_span_context().trace_id != 0
        assert provider.force_flush() is True  # 전송 실패여도 True를 반환한다.
        assert exporter.get_finished_spans() == ()
        provider.shutdown()
        spans = []

    def readback(url, timeout):
        assert parse_qs(urlparse(url).query)["trace_id"] == list(expected.values())
        assert timeout == 2
        if fault == "http_error":
            raise OSError("unavailable")
        if fault == "incomplete_read":
            raise IncompleteRead(b'{"data":')
        return io.StringIO(
            "{" if fault == "bad_json" else json.dumps({
                "data": spans, "next_cursor": "more" if fault == "pagination" else None,
            })
        )

    ticks = iter([0, 6])
    monkeypatch.setattr(agent_lab.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(agent_lab, "urlopen", readback)
    verified = agent_lab.verify_phoenix_traces(runs, run_id="test-only")
    if fault is None:
        assert verified == expected
    else:
        assert verified != expected
        assert len(verified) == (5 if fault in {
            "llm_missing", "root_missing", "wrong_parent", "wrong_run", "duplicate_id"
        } else 0)


def test_storage_check_waits_for_delayed_ingestion(monkeypatch, stored_agent_run):
    runs, spans = stored_agent_run
    responses = iter([[], spans])
    monkeypatch.setattr(agent_lab.time, "monotonic", lambda: 0)
    monkeypatch.setattr(agent_lab.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        agent_lab, "urlopen",
        lambda *args, **kwargs: io.StringIO(json.dumps({"data": next(responses)})),
    )
    assert agent_lab.verify_phoenix_traces(runs, run_id="test-only") == {
        run.sample_id: run.phoenix_trace_id for run in runs
    }


def test_storage_check_skips_network_without_trace_ids(monkeypatch):
    monkeypatch.setattr(agent_lab, "urlopen", lambda *args, **kwargs: pytest.fail("no HTTP"))
    assert agent_lab.verify_phoenix_traces([], run_id="test-only") == {}
