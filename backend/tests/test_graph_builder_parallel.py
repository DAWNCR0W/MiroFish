import time

import pytest

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


def test_add_text_batches_skips_failed_chunk_and_keeps_build_alive(monkeypatch, tmp_path):
    graph_root = tmp_path / "graphs"

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(Config, "LOCAL_GRAPH_FOLDER", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "GRAPH_ROOT", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "_locks", {})

    builder = GraphBuilderService()
    graph_id = builder.create_graph("partial-failure-test")
    builder.set_ontology(
        graph_id,
        {
            "entity_types": [{"name": "Person", "attributes": []}],
            "edge_types": [{"name": "KNOWS", "attributes": []}],
        },
    )

    def flaky_extract_chunk(self, chunk, ontology, known_entities):
        if chunk == "chunk-2":
            raise RuntimeError("llm unavailable")
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

    monkeypatch.setattr(GraphBuilderService, "_extract_chunk", flaky_extract_chunk)

    episode_ids = builder.add_text_batches(
        graph_id=graph_id,
        chunks=["chunk-1", "chunk-2", "chunk-3"],
        batch_size=3,
        parallel_workers=3,
    )

    graph = builder.store.get_graph(graph_id)
    batch_report = builder.get_last_batch_report()
    failed_episode = next(episode for episode in graph["episodes"] if episode["data"] == "chunk-2")

    assert len(episode_ids) == 3
    assert len(graph["nodes"]) == 2
    assert sum(1 for episode in graph["episodes"] if episode.get("processed")) == 3
    assert failed_episode["metadata"]["extraction_failed"] is True
    assert failed_episode["metadata"]["error"] == "llm unavailable"
    assert batch_report["succeeded_chunks"] == 2
    assert batch_report["failed_chunk_count"] == 1


def test_add_text_batches_still_fails_when_every_chunk_fails(monkeypatch, tmp_path):
    graph_root = tmp_path / "graphs"

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(Config, "LOCAL_GRAPH_FOLDER", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "GRAPH_ROOT", str(graph_root))
    monkeypatch.setattr(LocalGraphStore, "_locks", {})

    builder = GraphBuilderService()
    graph_id = builder.create_graph("all-failure-test")
    builder.set_ontology(
        graph_id,
        {
            "entity_types": [{"name": "Person", "attributes": []}],
            "edge_types": [{"name": "KNOWS", "attributes": []}],
        },
    )

    def always_fail(self, chunk, ontology, known_entities):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(GraphBuilderService, "_extract_chunk", always_fail)

    with pytest.raises(RuntimeError, match="모든 텍스트 청크 추출에 실패했습니다"):
        builder.add_text_batches(
            graph_id=graph_id,
            chunks=["chunk-1", "chunk-2"],
            batch_size=2,
            parallel_workers=2,
        )

    graph = builder.store.get_graph(graph_id)
    assert sum(1 for episode in graph["episodes"] if episode.get("processed")) == 2
