import time

from app.config import Config
from app.services.graph_builder import GraphBuilderService
from app.services.local_graph_extractor import LocalGraphExtractor
from app.services.local_graph_store import LocalGraphStore


def test_add_text_batches_parallelizes_chunk_extraction(monkeypatch, tmp_path):
    graph_root = tmp_path / "graphs"

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(Config, "LOCAL_GRAPH_FOLDER", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "GRAPH_ROOT", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "_locks", {})

    builder = GraphBuilderService()
    graph_id = builder.create_graph("parallel-test")
    builder.set_ontology(
        graph_id,
        {
            "entity_types": [{"name": "Person", "attributes": []}],
            "edge_types": [{"name": "KNOWS", "attributes": []}],
        },
    )

    def fake_extract_chunk(self, chunk, ontology, known_entities):
        time.sleep(0.2)
        return {
            "entities": [
                {
                    "name": chunk,
                    "type": "Person",
                    "summary": chunk,
                    "attributes": {},
                }
            ],
            "relationships": [],
            "summary": chunk,
        }

    monkeypatch.setattr(GraphBuilderService, "_extract_chunk", fake_extract_chunk)

    start = time.perf_counter()
    episode_ids = builder.add_text_batches(
        graph_id=graph_id,
        chunks=["chunk-1", "chunk-2", "chunk-3"],
        batch_size=3,
        parallel_workers=3,
    )
    elapsed = time.perf_counter() - start

    graph = builder.store.get_graph(graph_id)

    assert elapsed < 0.5
    assert len(episode_ids) == 3
    assert len(graph["nodes"]) == 3
    assert sum(1 for episode in graph["episodes"] if episode.get("processed")) == 3


def test_get_thread_extractor_preserves_custom_extractor_instance(monkeypatch, tmp_path):
    graph_root = tmp_path / "graphs"

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(LocalGraphStore, "GRAPH_ROOT", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "_locks", {})

    builder = GraphBuilderService()
    custom_extractor = LocalGraphExtractor.__new__(LocalGraphExtractor)
    custom_extractor.llm = object()
    builder.extractor = custom_extractor

    assert builder._get_thread_extractor() is custom_extractor
