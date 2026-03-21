import pytest

from app import create_app
from app.models.task import TaskManager, TaskStatus
from app.services.graph_builder import GraphBuilderService
from app.services.local_graph_extractor import LocalGraphExtractor


def test_graph_api_error_response_does_not_expose_traceback():
    app = create_app()

    with app.test_client() as client:
        response = client.get("/api/graph/data/non-existent-graph")

    payload = response.get_json()

    assert response.status_code == 404
    assert payload["success"] is False
    assert "traceback" not in payload


def test_graph_builder_worker_exposes_concise_task_error(monkeypatch):
    builder = GraphBuilderService()
    task_id = TaskManager().create_task("graph_build")

    def fail_create_graph(_name):
        raise RuntimeError("boom")

    monkeypatch.setattr(builder, "create_graph", fail_create_graph)

    builder._build_graph_worker(
        task_id=task_id,
        text="text",
        ontology={},
        graph_name="graph",
        chunk_size=500,
        chunk_overlap=50,
        batch_size=1,
        parallel_workers=1,
    )

    task = TaskManager().get_task(task_id)

    assert task is not None
    assert task.status == TaskStatus.FAILED
    assert "boom" in (task.error or "")
    assert "Traceback" not in (task.error or "")


class FailingLLMClient:
    def chat_json(self, messages, temperature=None, max_tokens=None):
        raise RuntimeError("llm unavailable")


def test_local_graph_extractor_raises_after_retry_exhaustion():
    extractor = LocalGraphExtractor(llm_client=FailingLLMClient())

    with pytest.raises(RuntimeError, match="그래프 추출에 반복 실패했습니다"):
        extractor.extract(
            text="sample",
            ontology={
                "entity_types": [{"name": "Person", "attributes": []}],
                "edge_types": [{"name": "KNOWS", "attributes": []}],
            },
        )
