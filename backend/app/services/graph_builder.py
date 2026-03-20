"""
그래프 구축 서비스
로컬 파일 저장과 LLM 추출을 사용해 지식 그래프를 구축합니다.
"""

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..models.task import TaskManager, TaskStatus
from .local_graph_extractor import LocalGraphExtractor
from .local_graph_store import LocalGraphStore
from .text_processor import TextProcessor


@dataclass
class GraphInfo:
    """그래프 정보"""

    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """
    그래프 구축 서비스
    외부 그래프 서비스 대신 로컬 저장소를 사용해 기존 API 계약을 유지합니다.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.task_manager = TaskManager()
        self.store = LocalGraphStore()
        self.extractor = LocalGraphExtractor()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
            daemon=True,
        )
        thread.start()
        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
    ) -> None:
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="그래프 구축을 시작합니다...",
            )

            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(task_id, progress=10, message=f"그래프가 생성되었습니다: {graph_id}")

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(task_id, progress=15, message="본체가 설정되었습니다")

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"텍스트를 {total_chunks}개 청크로 분할했습니다",
            )

            episode_uuids = self.add_text_batches(
                graph_id,
                chunks,
                batch_size,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),
                    message=msg,
                ),
            )

            self.task_manager.update_task(
                task_id,
                progress=60,
                message="로컬 추출 처리가 완료될 때까지 기다리는 중...",
            )
            self._wait_for_episodes(
                graph_id,
                episode_uuids,
                lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=60 + int(prog * 0.3),
                    message=msg,
                ),
            )

            self.task_manager.update_task(task_id, progress=90, message="그래프 정보를 가져오는 중...")
            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(
                task_id,
                {
                    "graph_id": graph_id,
                    "graph_info": graph_info.to_dict(),
                    "chunks_processed": total_chunks,
                },
            )
        except Exception as e:
            import traceback

            self.task_manager.fail_task(task_id, f"그래프 구축 실패: {e}\n{traceback.format_exc()}")

    def create_graph(self, name: str) -> str:
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.store.create_graph(
            graph_id=graph_id,
            name=name,
            description="MiroFish 로컬 그래프",
        )
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        self.store.save_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        episode_uuids: List[str] = []
        total_chunks = len(chunks)
        ontology = self.store.get_ontology(graph_id)

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size if total_chunks else 0

            if progress_callback:
                progress = (i + len(batch_chunks)) / total_chunks if total_chunks else 1.0
                progress_callback(
                    f"{batch_num}/{total_batches}번째 배치 데이터 처리 중 ({len(batch_chunks)}개 청크)...",
                    progress,
                )

            for chunk in batch_chunks:
                known_entities = [
                    {
                        "name": node.get("name", ""),
                        "type": next(
                            (
                                label for label in node.get("labels", [])
                                if label not in ["Entity", "Node"]
                            ),
                            "",
                        ),
                    }
                    for node in self.store.get_nodes(graph_id)
                ]
                episode = self.store.add_episode(graph_id, chunk, source="document")
                extraction = self.extractor.extract(
                    text=chunk,
                    ontology=ontology,
                    known_entities=known_entities,
                )
                self.store.apply_extraction(
                    graph_id=graph_id,
                    episode_id=episode["uuid"],
                    extraction=extraction,
                    created_at=episode["created_at"],
                )
                episode_uuids.append(episode["uuid"])

        return episode_uuids

    def _wait_for_episodes(
        self,
        graph_id: str,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600,
    ) -> None:
        if not episode_uuids:
            if progress_callback:
                progress_callback("대기할 필요가 없습니다(에피소드 없음)", 1.0)
            return

        start_time = time.time()
        pending_episodes = set(episode_uuids)
        total_episodes = len(episode_uuids)

        if progress_callback:
            progress_callback(f"{total_episodes}개 텍스트 블록 처리를 기다리기 시작합니다...", 0.0)

        while pending_episodes:
            for episode_uuid in list(pending_episodes):
                episode = self.store.get_episode(graph_id, episode_uuid)
                if episode and episode.get("processed"):
                    pending_episodes.remove(episode_uuid)

            completed_count = total_episodes - len(pending_episodes)
            if progress_callback:
                progress_callback(
                    f"로컬 처리 중... {completed_count}/{total_episodes} 완료",
                    completed_count / total_episodes if total_episodes else 1.0,
                )

            if not pending_episodes:
                break

            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        f"일부 텍스트 블록이 시간 초과되었습니다. 완료: {completed_count}/{total_episodes}",
                        completed_count / total_episodes if total_episodes else 1.0,
                    )
                break

            time.sleep(0.2)

        if progress_callback:
            progress_callback(f"처리 완료: {total_episodes - len(pending_episodes)}/{total_episodes}", 1.0)

    @staticmethod
    def _entity_types_from_nodes(nodes: List[Dict[str, Any]]) -> List[str]:
        entity_types = set()
        for node in nodes:
            for label in node.get("labels", []):
                if label not in ["Entity", "Node"]:
                    entity_types.add(label)
        return sorted(entity_types)

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        graph = self.store.get_graph(graph_id)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=self._entity_types_from_nodes(nodes),
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        graph = self.store.get_graph(graph_id)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        node_map = {node.get("uuid"): node.get("name", "") for node in nodes}

        nodes_data = [
            {
                "uuid": node.get("uuid"),
                "name": node.get("name"),
                "labels": node.get("labels", []),
                "summary": node.get("summary", ""),
                "attributes": node.get("attributes", {}),
                "created_at": node.get("created_at"),
            }
            for node in nodes
        ]

        edges_data = [
            {
                "uuid": edge.get("uuid"),
                "name": edge.get("name", ""),
                "fact": edge.get("fact", ""),
                "fact_type": edge.get("fact_type") or edge.get("name", ""),
                "source_node_uuid": edge.get("source_node_uuid", ""),
                "target_node_uuid": edge.get("target_node_uuid", ""),
                "source_node_name": node_map.get(edge.get("source_node_uuid", ""), ""),
                "target_node_name": node_map.get(edge.get("target_node_uuid", ""), ""),
                "attributes": edge.get("attributes", {}),
                "created_at": edge.get("created_at"),
                "valid_at": edge.get("valid_at"),
                "invalid_at": edge.get("invalid_at"),
                "expired_at": edge.get("expired_at"),
                "episodes": edge.get("episodes", []),
            }
            for edge in edges
        ]

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str) -> None:
        self.store.delete_graph(graph_id)
