"""
그래프 구축 서비스
로컬 파일 저장과 LLM 추출을 사용해 지식 그래프를 구축합니다.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .graph_entity_deduper import GraphEntityDeduper
from .local_graph_extractor import LocalGraphExtractor
from .local_graph_store import LocalGraphStore
from .text_processor import TextProcessor

logger = get_logger("mirofish.graph_builder")


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


@dataclass
class BatchProcessingReport:
    """최근 배치 처리 결과 요약"""

    total_chunks: int = 0
    succeeded_chunks: int = 0
    episode_uuids: List[str] = field(default_factory=list)
    failed_chunks: List[Dict[str, str]] = field(default_factory=list)

    @property
    def failed_chunk_count(self) -> int:
        return len(self.failed_chunks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_chunks": self.total_chunks,
            "succeeded_chunks": self.succeeded_chunks,
            "failed_chunk_count": self.failed_chunk_count,
            "failed_chunks": list(self.failed_chunks),
        }


class GraphBuilderService:
    """
    그래프 구축 서비스
    외부 그래프 서비스 대신 로컬 저장소를 사용해 기존 API 계약을 유지합니다.
    """

    MAX_BATCH_PARALLEL_WORKERS = Config.GRAPH_BUILD_MAX_PARALLEL_WORKERS

    def __init__(self, api_key: Optional[str] = None):
        self.task_manager = TaskManager()
        self.store = LocalGraphStore()
        self.extractor = LocalGraphExtractor()
        self._extractor_local = threading.local()
        self._last_batch_report = BatchProcessingReport()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
        parallel_workers: Optional[int] = None,
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
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, parallel_workers),
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
        parallel_workers: Optional[int] = None,
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
                batch_size=batch_size,
                progress_callback=lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.4),
                    message=msg,
                ),
                parallel_workers=parallel_workers,
            )
            batch_report = self.get_last_batch_report()

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
                    "succeeded_chunks": batch_report["succeeded_chunks"],
                    "failed_chunk_count": batch_report["failed_chunk_count"],
                },
            )
        except Exception as e:
            logger.exception("그래프 구축 워커 실패: task_id=%s", task_id)
            self.task_manager.fail_task(task_id, f"그래프 구축 실패: {e}")

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

    @staticmethod
    def _custom_label(node: Dict[str, Any]) -> str:
        return next(
            (
                label for label in node.get("labels", [])
                if label not in ["Entity", "Node"]
            ),
            "",
        )

    def _snapshot_known_entities(self, graph_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "name": node.get("name", ""),
                "type": self._custom_label(node),
                "aliases": node.get("aliases", []) or [],
            }
            for node in self.store.get_nodes(graph_id)
        ]

    def _resolve_parallel_workers(
        self,
        total_items: int,
        batch_size: int,
        parallel_workers: Optional[int] = None,
    ) -> int:
        if total_items <= 1:
            return 1

        if parallel_workers is None:
            parallel_workers = LLMClient.get_recommended_parallel_requests(
                fallback=Config.GRAPH_BUILD_PARALLEL_WORKERS,
                max_cap=self.MAX_BATCH_PARALLEL_WORKERS,
            )

        try:
            resolved = int(parallel_workers)
        except (TypeError, ValueError):
            resolved = 1

        return max(1, min(resolved, total_items, self.MAX_BATCH_PARALLEL_WORKERS))

    def _extract_chunk(
        self,
        chunk: str,
        ontology: Dict[str, Any],
        known_entities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._get_thread_extractor().extract(
            text=chunk,
            ontology=ontology,
            known_entities=known_entities,
        )

    def _get_thread_extractor(self):
        base_extractor = getattr(self, "extractor", None)
        thread_local = getattr(self, "_extractor_local", None)

        if base_extractor is None or thread_local is None or not isinstance(base_extractor, LocalGraphExtractor):
            return base_extractor

        extractor = getattr(thread_local, "extractor", None)
        extractor_source_id = getattr(thread_local, "extractor_source_id", None)
        if extractor is None or extractor_source_id != id(base_extractor):
            extractor = base_extractor
            thread_local.extractor = extractor
            thread_local.extractor_source_id = id(base_extractor)
        return extractor

    def _process_batch_wave(
        self,
        graph_id: str,
        wave_chunks: List[str],
        ontology: Dict[str, Any],
        parallel_workers: int,
    ) -> BatchProcessingReport:
        if not wave_chunks:
            return BatchProcessingReport()

        wave_known_entities = self._snapshot_known_entities(graph_id)
        wave_records: List[Dict[str, Any]] = []

        for chunk in wave_chunks:
            episode = self.store.add_episode(graph_id, chunk, source="document")
            wave_records.append({
                "chunk": chunk,
                "episode": episode,
            })

        if len(wave_records) == 1 or parallel_workers <= 1:
            for record in wave_records:
                try:
                    record["extraction"] = self._extract_chunk(
                        record["chunk"],
                        ontology,
                        wave_known_entities,
                    )
                except Exception as exc:
                    record["error"] = exc
        else:
            with ThreadPoolExecutor(max_workers=min(parallel_workers, len(wave_records))) as executor:
                future_to_index = {
                    executor.submit(
                        self._extract_chunk,
                        record["chunk"],
                        ontology,
                        wave_known_entities,
                    ): index
                    for index, record in enumerate(wave_records)
                }

                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        wave_records[index]["extraction"] = future.result()
                    except Exception as exc:
                        wave_records[index]["error"] = exc

        report = BatchProcessingReport(total_chunks=len(wave_records))
        for record in wave_records:
            episode_id = record["episode"]["uuid"]
            report.episode_uuids.append(episode_id)
            error = record.get("error")
            if error is not None:
                error_text = str(error) or error.__class__.__name__
                chunk_preview = record["chunk"].replace("\n", " ").strip()[:120]
                logger.warning(
                    "청크 추출 실패 후 해당 청크를 건너뜁니다: graph_id=%s, episode_id=%s, error=%s, chunk_preview=%s",
                    graph_id,
                    episode_id,
                    error_text,
                    chunk_preview,
                )
                self.store.mark_episode_processed(
                    graph_id,
                    episode_id,
                    metadata={
                        "extraction_failed": True,
                        "error": error_text,
                    },
                )
                report.failed_chunks.append(
                    {
                        "episode_id": episode_id,
                        "error": error_text,
                        "chunk_preview": chunk_preview,
                    }
                )
                continue

            self.store.apply_extraction(
                graph_id=graph_id,
                episode_id=episode_id,
                extraction=record["extraction"],
                created_at=record["episode"]["created_at"],
            )
            report.succeeded_chunks += 1

        return report

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
        parallel_workers: Optional[int] = None,
    ) -> List[str]:
        episode_uuids: List[str] = []
        total_chunks = len(chunks)
        ontology = self.store.get_ontology(graph_id)
        completed_chunks = 0
        failed_chunks: List[Dict[str, str]] = []
        succeeded_chunks = 0
        effective_workers = self._resolve_parallel_workers(
            total_items=total_chunks,
            batch_size=batch_size,
            parallel_workers=parallel_workers,
        )

        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size if total_chunks else 0

            if progress_callback:
                progress = completed_chunks / total_chunks if total_chunks else 1.0
                progress_callback(
                    f"{batch_num}/{total_batches}번째 배치 데이터 처리 중 ({len(batch_chunks)}개 청크)...",
                    progress,
                )

            batch_report = self._process_batch_wave(
                graph_id=graph_id,
                wave_chunks=batch_chunks,
                ontology=ontology,
                parallel_workers=effective_workers,
            )
            episode_uuids.extend(batch_report.episode_uuids)
            completed_chunks += len(batch_chunks)
            succeeded_chunks += batch_report.succeeded_chunks
            failed_chunks.extend(batch_report.failed_chunks)

            if progress_callback:
                failure_suffix = f", 실패 {len(failed_chunks)}개 건너뜀" if failed_chunks else ""
                progress_callback(
                    f"{batch_num}/{total_batches}번째 배치 처리 완료 ({completed_chunks}/{total_chunks}개 청크{failure_suffix})...",
                    completed_chunks / total_chunks if total_chunks else 1.0,
                )

        self._last_batch_report = BatchProcessingReport(
            total_chunks=total_chunks,
            succeeded_chunks=succeeded_chunks,
            failed_chunks=failed_chunks,
        )

        if total_chunks and succeeded_chunks == 0:
            first_error = failed_chunks[0]["error"] if failed_chunks else "알 수 없는 오류"
            raise RuntimeError(f"모든 텍스트 청크 추출에 실패했습니다: {first_error}")

        if failed_chunks:
            logger.warning(
                "그래프 배치 처리 중 일부 청크 추출 실패: graph_id=%s, succeeded=%s, failed=%s",
                graph_id,
                succeeded_chunks,
                len(failed_chunks),
            )

        return episode_uuids

    def get_last_batch_report(self) -> Dict[str, Any]:
        return self._last_batch_report.to_dict()

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
                "aliases": node.get("aliases", []) or [],
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

    def dedupe_graph_entities(self, graph_id: str, dry_run: bool = True) -> Dict[str, Any]:
        deduper = GraphEntityDeduper(store=self.store)
        return deduper.dedupe_graph(graph_id=graph_id, dry_run=dry_run)

    def delete_graph(self, graph_id: str) -> None:
        self.store.delete_graph(graph_id)
