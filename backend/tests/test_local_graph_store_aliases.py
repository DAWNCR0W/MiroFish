from app.config import Config
from app.services.graph_entity_deduper import GraphEntityDeduper
from app.services.local_graph_store import LocalGraphStore


def _create_store(monkeypatch, tmp_path):
    graph_root = tmp_path / "graphs"

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(LocalGraphStore, "GRAPH_ROOT", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "_locks", {})

    store = LocalGraphStore()
    graph_id = "alias-test"
    store.create_graph(graph_id, "alias-test")
    return store, graph_id


def test_find_node_by_name_matches_alias(monkeypatch, tmp_path):
    store, graph_id = _create_store(monkeypatch, tmp_path)

    store.add_episode(graph_id, "ep1", episode_id="ep1")
    store.apply_extraction(
        graph_id,
        "ep1",
        {
            "entities": [
                {
                    "name": "Korea University",
                    "type": "Organization",
                    "aliases": ["高麗大學校", "고려대학교"],
                    "summary": "대한민국 서울의 주요 대학",
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": "",
        },
    )

    matched = store.find_node_by_name(graph_id, "고려대학교", "Organization")

    assert matched is not None
    assert matched["name"] == "Korea University"
    assert set(matched.get("aliases", [])) == {"高麗大學校", "고려대학교"}


def test_apply_extraction_merges_multilingual_alias_entities(monkeypatch, tmp_path):
    store, graph_id = _create_store(monkeypatch, tmp_path)

    store.add_episode(graph_id, "ep1", episode_id="ep1")
    store.apply_extraction(
        graph_id,
        "ep1",
        {
            "entities": [
                {
                    "name": "Korea University",
                    "type": "Organization",
                    "aliases": ["高麗大學校"],
                    "summary": "대한민국 서울의 주요 대학",
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": "",
        },
    )

    store.add_episode(graph_id, "ep2", episode_id="ep2")
    store.apply_extraction(
        graph_id,
        "ep2",
        {
            "entities": [
                {
                    "name": "고려대학교",
                    "type": "Organization",
                    "aliases": ["Korea University"],
                    "summary": "서울에 있는 대학",
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": "",
        },
    )

    graph = store.get_graph(graph_id)

    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["name"] == "Korea University"
    assert set(graph["nodes"][0].get("aliases", [])) == {"高麗大學校", "고려대학교"}


def test_merge_nodes_redirects_edges_and_preserves_aliases(monkeypatch, tmp_path):
    store, graph_id = _create_store(monkeypatch, tmp_path)

    store.add_episode(graph_id, "ep1", episode_id="ep1")
    store.apply_extraction(
        graph_id,
        "ep1",
        {
            "entities": [
                {"name": "Korea University", "type": "Organization", "summary": "", "attributes": {}},
                {"name": "Student A", "type": "Person", "summary": "", "attributes": {}},
            ],
            "relationships": [
                {
                    "type": "AFFILIATED_WITH",
                    "source_name": "Student A",
                    "source_type": "Person",
                    "target_name": "Korea University",
                    "target_type": "Organization",
                    "fact": "Student A는 Korea University와 관련이 있다",
                    "attributes": {},
                }
            ],
            "summary": "",
        },
    )

    store.add_episode(graph_id, "ep2", episode_id="ep2")
    store.apply_extraction(
        graph_id,
        "ep2",
        {
            "entities": [
                {"name": "고려대학교", "type": "Organization", "summary": "", "attributes": {}},
                {"name": "Student A", "type": "Person", "summary": "", "attributes": {}},
            ],
            "relationships": [
                {
                    "type": "AFFILIATED_WITH",
                    "source_name": "Student A",
                    "source_type": "Person",
                    "target_name": "고려대학교",
                    "target_type": "Organization",
                    "fact": "Student A는 Korea University와 관련이 있다",
                    "attributes": {},
                }
            ],
            "summary": "",
        },
    )

    graph_before = store.get_graph(graph_id)
    graph_before["edges"][0]["invalid_at"] = "2026-03-01T00:00:00"
    store._write_graph(graph_id, graph_before)
    graph_before = store.get_graph(graph_id)
    canonical_uuid = next(node["uuid"] for node in graph_before["nodes"] if node["name"] == "Korea University")
    localized_uuid = next(node["uuid"] for node in graph_before["nodes"] if node["name"] == "고려대학교")

    result = store.merge_nodes(graph_id, canonical_uuid, [localized_uuid])
    graph_after = store.get_graph(graph_id)

    assert result["merged_count"] == 1
    assert result["removed_edges"] == 1
    assert len(graph_after["nodes"]) == 2
    assert len(graph_after["edges"]) == 1

    merged = next(node for node in graph_after["nodes"] if node["uuid"] == canonical_uuid)
    assert "고려대학교" in merged.get("aliases", [])
    assert graph_after["edges"][0]["target_node_uuid"] == canonical_uuid
    assert graph_after["edges"][0]["invalid_at"] is None


class StaticMergeLLM:
    def __init__(self, merge_groups):
        self.merge_groups = merge_groups

    def chat_json(self, messages, temperature=None, max_tokens=None):
        return {
            "merge_groups": self.merge_groups,
            "summary": "병합 후보를 찾았습니다.",
        }


def test_graph_entity_deduper_merges_existing_multilingual_nodes(monkeypatch, tmp_path):
    store, graph_id = _create_store(monkeypatch, tmp_path)

    store.add_episode(graph_id, "ep1", episode_id="ep1")
    store.apply_extraction(
        graph_id,
        "ep1",
        {
            "entities": [
                {
                    "name": "Korea University",
                    "type": "Organization",
                    "summary": "대한민국 서울의 대학",
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": "",
        },
    )

    store.add_episode(graph_id, "ep2", episode_id="ep2")
    store.apply_extraction(
        graph_id,
        "ep2",
        {
            "entities": [
                {
                    "name": "고려대학교",
                    "type": "Organization",
                    "summary": "서울에 있는 대학",
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": "",
        },
    )

    graph = store.get_graph(graph_id)
    merge_groups = [[node["uuid"] for node in graph["nodes"]]]
    deduper = GraphEntityDeduper(
        llm_client=StaticMergeLLM(merge_groups),
        store=store,
    )

    result = deduper.dedupe_graph(graph_id, dry_run=False)
    merged_graph = store.get_graph(graph_id)

    assert result["merged_group_count"] == 1
    assert result["merged_node_count"] == 1
    assert len(merged_graph["nodes"]) == 1
    assert set(merged_graph["nodes"][0].get("aliases", [])) == {"고려대학교"}
