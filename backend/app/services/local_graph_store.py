"""
로컬 그래프 저장소
그래프 데이터를 JSON 파일로 저장하고 조회한다.
"""

import copy
import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.ontology import normalize_ontology


class LocalGraphStore:
    """파일 기반 그래프 저장소"""

    GRAPH_ROOT = os.path.join(Config.UPLOAD_FOLDER, "graphs")

    _locks: Dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    @classmethod
    def _ensure_root(cls) -> None:
        os.makedirs(cls.GRAPH_ROOT, exist_ok=True)

    @classmethod
    def _graph_dir(cls, graph_id: str) -> str:
        cls._ensure_root()
        return os.path.join(cls.GRAPH_ROOT, graph_id)

    @classmethod
    def _graph_path(cls, graph_id: str) -> str:
        return os.path.join(cls._graph_dir(graph_id), "graph.json")

    @classmethod
    def _lock_for(cls, graph_id: str) -> threading.Lock:
        with cls._locks_guard:
            if graph_id not in cls._locks:
                cls._locks[graph_id] = threading.Lock()
            return cls._locks[graph_id]

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not name:
            return ""
        normalized = "".join(ch.lower() for ch in name.strip() if ch.isalnum())
        return normalized

    @staticmethod
    def _custom_labels(labels: List[str]) -> List[str]:
        return [label for label in labels if label not in ["Entity", "Node"]]

    def create_graph(self, graph_id: str, name: str, description: Optional[str] = None) -> None:
        graph_dir = self._graph_dir(graph_id)
        os.makedirs(graph_dir, exist_ok=True)

        now = self._now()
        graph = {
            "graph_id": graph_id,
            "name": name,
            "description": description or "",
            "created_at": now,
            "updated_at": now,
            "ontology": None,
            "nodes": [],
            "edges": [],
            "episodes": [],
        }
        self._write_graph(graph_id, graph)

    def _read_graph(self, graph_id: str) -> Dict[str, Any]:
        graph_path = self._graph_path(graph_id)
        if not os.path.exists(graph_path):
            raise FileNotFoundError(f"그래프가 존재하지 않음: {graph_id}")

        with open(graph_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_graph(self, graph_id: str, graph: Dict[str, Any]) -> None:
        graph["updated_at"] = self._now()
        graph_dir = self._graph_dir(graph_id)
        os.makedirs(graph_dir, exist_ok=True)
        with open(self._graph_path(graph_id), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    def get_graph(self, graph_id: str) -> Dict[str, Any]:
        with self._lock_for(graph_id):
            return copy.deepcopy(self._read_graph(graph_id))

    def save_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            graph["ontology"] = normalize_ontology(ontology)
            self._write_graph(graph_id, graph)

    def get_ontology(self, graph_id: str) -> Dict[str, Any]:
        graph = self.get_graph(graph_id)
        return normalize_ontology(graph.get("ontology"))

    def add_episode(
        self,
        graph_id: str,
        text: str,
        source: str = "document",
        metadata: Optional[Dict[str, Any]] = None,
        episode_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        episode = {
            "uuid": episode_id or f"ep_{uuid.uuid4().hex[:16]}",
            "type": "text",
            "data": text,
            "source": source,
            "processed": False,
            "created_at": created_at or self._now(),
            "metadata": metadata or {},
        }

        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            graph.setdefault("episodes", []).append(episode)
            self._write_graph(graph_id, graph)

        return copy.deepcopy(episode)

    def get_episode(self, graph_id: str, episode_id: str) -> Optional[Dict[str, Any]]:
        graph = self.get_graph(graph_id)
        for episode in graph.get("episodes", []):
            if episode.get("uuid") == episode_id:
                return episode
        return None

    def get_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph(graph_id).get("nodes", [])

    def get_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph(graph_id).get("edges", [])

    def get_node(self, graph_id: str, node_uuid: str) -> Optional[Dict[str, Any]]:
        graph = self.get_graph(graph_id)
        for node in graph.get("nodes", []):
            if node.get("uuid") == node_uuid:
                return node
        return None

    def find_node_by_name(
        self,
        graph_id: str,
        name: str,
        entity_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_name = self._normalize_name(name)
        if not normalized_name:
            return None

        graph = self.get_graph(graph_id)
        candidates = []
        for node in graph.get("nodes", []):
            if self._normalize_name(node.get("name", "")) == normalized_name:
                candidates.append(node)

        if not candidates:
            return None

        if entity_type:
            for candidate in candidates:
                if entity_type in self._custom_labels(candidate.get("labels", [])):
                    return candidate

        return candidates[0]

    def apply_extraction(
        self,
        graph_id: str,
        episode_id: str,
        extraction: Dict[str, Any],
        created_at: Optional[str] = None,
    ) -> Dict[str, int]:
        created_at = created_at or self._now()

        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            nodes = graph.setdefault("nodes", [])
            edges = graph.setdefault("edges", [])
            episodes = graph.setdefault("episodes", [])

            upserted_nodes: Dict[str, Dict[str, Any]] = {}
            added_nodes = 0
            added_edges = 0

            def find_existing_node(name: str, entity_type: Optional[str]) -> Optional[Dict[str, Any]]:
                normalized_name = self._normalize_name(name)
                if not normalized_name:
                    return None

                same_name = [
                    node for node in nodes
                    if self._normalize_name(node.get("name", "")) == normalized_name
                ]
                if not same_name:
                    return None

                if entity_type:
                    for node in same_name:
                        if entity_type in self._custom_labels(node.get("labels", [])):
                            return node
                return same_name[0]

            def merge_attributes(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
                merged = dict(existing or {})
                for key, value in (incoming or {}).items():
                    if value not in [None, "", [], {}]:
                        merged[key] = value
                return merged

            def upsert_node(entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                nonlocal added_nodes

                name = (entity.get("name") or "").strip()
                entity_type = (entity.get("type") or "").strip()
                if not name:
                    return None

                cache_key = f"{self._normalize_name(name)}::{entity_type.lower()}"
                if cache_key in upserted_nodes:
                    return upserted_nodes[cache_key]

                labels = ["Entity"]
                if entity_type:
                    labels.append(entity_type)

                existing = find_existing_node(name, entity_type)
                if existing:
                    existing_labels = existing.get("labels", [])
                    for label in labels:
                        if label not in existing_labels:
                            existing_labels.append(label)
                    existing["labels"] = existing_labels

                    incoming_summary = (entity.get("summary") or "").strip()
                    existing_summary = (existing.get("summary") or "").strip()
                    if incoming_summary and incoming_summary not in existing_summary:
                        if not existing_summary:
                            existing["summary"] = incoming_summary
                        elif len(incoming_summary) > len(existing_summary):
                            existing["summary"] = incoming_summary

                    existing["attributes"] = merge_attributes(
                        existing.get("attributes") or {},
                        entity.get("attributes") or {},
                    )
                    existing.setdefault("episodes", [])
                    if episode_id not in existing["episodes"]:
                        existing["episodes"].append(episode_id)
                    upserted_nodes[cache_key] = existing
                    return existing

                node = {
                    "uuid": f"node_{uuid.uuid4().hex[:16]}",
                    "name": name,
                    "labels": labels,
                    "summary": (entity.get("summary") or "").strip(),
                    "attributes": entity.get("attributes") or {},
                    "created_at": created_at,
                    "episodes": [episode_id],
                }
                nodes.append(node)
                added_nodes += 1
                upserted_nodes[cache_key] = node
                return node

            for entity in extraction.get("entities", []):
                upsert_node(entity)

            for relation in extraction.get("relationships", []):
                source = upsert_node({
                    "name": relation.get("source_name"),
                    "type": relation.get("source_type"),
                    "summary": relation.get("source_summary", ""),
                    "attributes": relation.get("source_attributes", {}),
                })
                target = upsert_node({
                    "name": relation.get("target_name"),
                    "type": relation.get("target_type"),
                    "summary": relation.get("target_summary", ""),
                    "attributes": relation.get("target_attributes", {}),
                })
                relation_type = (relation.get("type") or "").strip()
                fact = (relation.get("fact") or "").strip()

                if not source or not target or not relation_type:
                    continue

                duplicate = next(
                    (
                        edge for edge in edges
                        if edge.get("name") == relation_type
                        and edge.get("source_node_uuid") == source.get("uuid")
                        and edge.get("target_node_uuid") == target.get("uuid")
                        and edge.get("fact") == fact
                    ),
                    None,
                )
                if duplicate:
                    duplicate.setdefault("episodes", [])
                    if episode_id not in duplicate["episodes"]:
                        duplicate["episodes"].append(episode_id)
                    duplicate["attributes"] = merge_attributes(
                        duplicate.get("attributes") or {},
                        relation.get("attributes") or {},
                    )
                    continue

                edges.append({
                    "uuid": f"edge_{uuid.uuid4().hex[:16]}",
                    "name": relation_type,
                    "fact": fact,
                    "fact_type": relation_type,
                    "source_node_uuid": source.get("uuid"),
                    "target_node_uuid": target.get("uuid"),
                    "attributes": relation.get("attributes") or {},
                    "created_at": created_at,
                    "valid_at": created_at,
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": [episode_id],
                })
                added_edges += 1

            summary = (extraction.get("summary") or "").strip()
            for episode in episodes:
                if episode.get("uuid") == episode_id:
                    episode["processed"] = True
                    if summary:
                        episode.setdefault("metadata", {})
                        episode["metadata"]["summary"] = summary
                    break

            self._write_graph(graph_id, graph)

        return {
            "added_nodes": added_nodes,
            "added_edges": added_edges,
        }

    def mark_episode_processed(self, graph_id: str, episode_id: str) -> None:
        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            for episode in graph.get("episodes", []):
                if episode.get("uuid") == episode_id:
                    episode["processed"] = True
                    break
            self._write_graph(graph_id, graph)

    def delete_graph(self, graph_id: str) -> None:
        graph_dir = self._graph_dir(graph_id)
        if os.path.exists(graph_dir):
            shutil.rmtree(graph_dir)

        with self._locks_guard:
            self._locks.pop(graph_id, None)
