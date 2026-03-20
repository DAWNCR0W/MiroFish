import json

from app.config import Config
from app.services.graph_tools import GraphToolsService


def _write_graph(tmp_path, graph_id, payload):
    graph_dir = tmp_path / "graphs" / graph_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "graph.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_get_entity_summary_matches_alias(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))

    graph_id = "graph-alias"
    _write_graph(
        tmp_path,
        graph_id,
        {
            "graph_id": graph_id,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Wuhan University",
                    "aliases": ["우한대학교", "武汉大学"],
                    "labels": ["Entity", "Organization"],
                    "summary": "중국 우한의 주요 대학",
                    "attributes": {},
                }
            ],
            "edges": [],
        },
    )

    service = GraphToolsService()
    result = service.get_entity_summary(graph_id, "우한대학교")

    assert result["entity_info"] is not None
    assert result["entity_info"]["name"] == "Wuhan University"
    assert set(result["entity_info"]["aliases"]) == {"우한대학교", "武汉大学"}


def test_insight_forge_handles_edges_with_missing_node_records(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))

    graph_id = "graph-missing-node"
    _write_graph(
        tmp_path,
        graph_id,
        {
            "graph_id": graph_id,
            "nodes": [],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "RESPONDS_TO",
                    "fact": "우한대학교는 사건에 대응했다",
                    "source_node_uuid": "missing-source",
                    "target_node_uuid": "missing-target",
                    "attributes": {},
                    "created_at": "2026-03-21T00:00:00",
                    "valid_at": "2026-03-21T00:00:00",
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": [],
                }
            ],
        },
    )

    service = GraphToolsService()
    monkeypatch.setattr(
        service,
        "_generate_sub_queries",
        lambda query, simulation_requirement, report_context="", max_queries=5: [query],
    )

    result = service.insight_forge(
        graph_id=graph_id,
        query="대응",
        simulation_requirement="반응 분석",
    )

    assert result.total_relationships == 1
    assert "missing-" in result.relationship_chains[0]
