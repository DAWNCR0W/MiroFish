"""
로컬 그래프 검색 도구 서비스.

보고서 생성과 에이전트 인물 설정 강화를 위해 필요한 그래프 조회, 검색, 인터뷰 기능을 제공합니다.
"""

import csv
import glob
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.graph_tools")


@dataclass
class SearchResult:
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count,
        }

    def to_text(self) -> str:
        lines = [f"검색어: {self.query}", f"관련 정보 {self.total_count}건을 찾았습니다"]
        if self.facts:
            lines.append("\n### 관련 사실:")
            for index, fact in enumerate(self.facts, 1):
                lines.append(f"{index}. {fact}")
        return "\n".join(lines)


@dataclass
class NodeInfo:
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
        }

    def to_text(self) -> str:
        entity_type = next((label for label in self.labels if label not in ["Entity", "Node"]), "미상 유형")
        return f"엔티티: {self.name} (유형: {entity_type})\n요약: {self.summary}"


@dataclass
class EdgeInfo:
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    episodes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
            "attributes": self.attributes,
            "episodes": self.episodes,
        }

    def to_text(self, include_temporal: bool = False) -> str:
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        text = f"관계: {source} --[{self.name}]--> {target}\n사실: {self.fact}"
        if include_temporal:
            valid_at = self.valid_at or "미상"
            invalid_at = self.invalid_at or "현재까지"
            text += f"\n시효: {valid_at} - {invalid_at}"
            if self.expired_at:
                text += f" (만료됨: {self.expired_at})"
        return text

    @property
    def is_expired(self) -> bool:
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    semantic_facts: List[str] = field(default_factory=list)
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)
    relationship_chains: List[str] = field(default_factory=list)
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
        }

    def to_text(self) -> str:
        parts = [
            "## 심층 예측 분석",
            f"분석 질문: {self.query}",
            f"예측 시나리오: {self.simulation_requirement}",
            "\n### 예측 데이터 통계",
            f"- 관련 예측 사실: {self.total_facts}건",
            f"- 관련 엔티티: {self.total_entities}개",
            f"- 관계 사슬: {self.total_relationships}건",
        ]
        if self.sub_queries:
            parts.append("\n### 분석된 하위 질문")
            for index, sub_query in enumerate(self.sub_queries, 1):
                parts.append(f"{index}. {sub_query}")
        if self.semantic_facts:
            parts.append("\n### 【핵심 사실】(보고서에서 이 원문을 인용하세요)")
            for index, fact in enumerate(self.semantic_facts, 1):
                parts.append(f'{index}. "{fact}"')
        if self.entity_insights:
            parts.append("\n### 【핵심 엔티티】")
            for entity in self.entity_insights:
                parts.append(f"- **{entity.get('name', '미상')}** ({entity.get('type', '엔티티')})")
                if entity.get("summary"):
                    parts.append(f'  요약: "{entity.get("summary")}"')
                if entity.get("related_facts"):
                    parts.append(f"  관련 사실: {len(entity.get('related_facts', []))}건")
        if self.relationship_chains:
            parts.append("\n### 【관계 사슬】")
            for chain in self.relationship_chains:
                parts.append(f"- {chain}")
        return "\n".join(parts)


@dataclass
class PanoramaResult:
    query: str
    all_nodes: List[NodeInfo] = field(default_factory=list)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    active_facts: List[str] = field(default_factory=list)
    historical_facts: List[str] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [node.to_dict() for node in self.all_nodes],
            "all_edges": [edge.to_dict() for edge in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count,
        }

    def to_text(self) -> str:
        parts = [
            "## 폭넓은 검색 결과(미래 전경 뷰)",
            f"질문: {self.query}",
            "\n### 통계 정보",
            f"- 총 노드 수: {self.total_nodes}",
            f"- 총 엣지 수: {self.total_edges}",
            f"- 현재 유효 사실: {self.active_count}건",
            f"- 과거/만료 사실: {self.historical_count}건",
        ]
        if self.active_facts:
            parts.append("\n### 【현재 유효 사실】(시뮬레이션 최신 결과)")
            for index, fact in enumerate(self.active_facts, 1):
                parts.append(f'{index}. "{fact}"')
        if self.historical_facts:
            parts.append("\n### 【과거/만료 사실】(변천 과정 기록)")
            for index, fact in enumerate(self.historical_facts, 1):
                parts.append(f'{index}. "{fact}"')
        if self.all_nodes:
            parts.append("\n### 【관련 엔티티】")
            for node in self.all_nodes:
                entity_type = next((label for label in node.labels if label not in ["Entity", "Node"]), "엔티티")
                parts.append(f"- **{node.name}** ({entity_type})")
        return "\n".join(parts)


@dataclass
class AgentInterview:
    agent_name: str
    agent_role: str
    agent_bio: str
    question: str
    response: str
    key_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes,
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_소개: {self.agent_bio}_\n\n"
        text += f"**질문:** {self.question}\n\n"
        text += f"**답변:** {self.response}\n"
        if self.key_quotes:
            text += "\n**핵심 인용:**\n"
            for quote in self.key_quotes:
                text += f'> "{quote.strip()}"\n'
        return text


@dataclass
class InterviewResult:
    interview_topic: str
    interview_questions: List[str]
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    interviews: List[AgentInterview] = field(default_factory=list)
    selection_reasoning: str = ""
    summary: str = ""
    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [item.to_dict() for item in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count,
        }

    def to_text(self) -> str:
        parts = [
            "## 심층 인터뷰 보고서",
            f"**인터뷰 주제:** {self.interview_topic}",
            f"**인터뷰 인원:** {self.interviewed_count} / {self.total_agents} 명의 시뮬레이션 에이전트",
            "\n### 인터뷰 대상 선택 이유",
            self.selection_reasoning or "(자동 선택)",
            "\n---",
            "\n### 인터뷰 기록",
        ]
        if self.interviews:
            for index, interview in enumerate(self.interviews, 1):
                parts.append(f"\n#### 인터뷰 #{index}: {interview.agent_name}")
                parts.append(interview.to_text())
                parts.append("\n---")
        else:
            parts.append("(인터뷰 기록 없음)\n\n---")
        parts.append("\n### 인터뷰 요약 및 핵심 관점")
        parts.append(self.summary or "(요약 없음)")
        return "\n".join(parts)


class GraphToolsService:
    """로컬 그래프 도구 서비스입니다."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client
        logger.info("그래프 도구 서비스 초기화 완료")

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _find_graph_file(self, graph_id: str) -> str:
        candidates = [
            os.path.join(Config.UPLOAD_FOLDER, "graphs", graph_id, "graph.json"),
            os.path.join(Config.UPLOAD_FOLDER, "projects", "*", "graphs", graph_id, "graph.json"),
            os.path.join(Config.UPLOAD_FOLDER, "projects", "*", graph_id, "graph.json"),
            os.path.join(Config.UPLOAD_FOLDER, "projects", "*", "graphs", graph_id, "data.json"),
            os.path.join(Config.UPLOAD_FOLDER, "graphs", graph_id, "data.json"),
        ]
        for pattern in candidates:
            for path in glob.glob(pattern):
                if os.path.isfile(path):
                    return path
        raise FileNotFoundError(f"그래프 파일을 찾을 수 없습니다: {graph_id}")

    def _load_graph_data(self, graph_id: str) -> Dict[str, Any]:
        path = self._find_graph_file(graph_id)
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if data.get("graph_id") and data["graph_id"] != graph_id:
            raise ValueError(f"그래프 파일이 요청한 graph_id와 일치하지 않습니다: {graph_id}")
        return data

    def _build_node_map(self, graph_id: str) -> Dict[str, Dict[str, Any]]:
        data = self._load_graph_data(graph_id)
        return {node.get("uuid", ""): node for node in data.get("nodes", []) if node.get("uuid")}

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        if not text:
            return []
        return [token for token in re.split(r"[\s,，。；;：:、/]+", text.lower()) if len(token) > 1]

    @staticmethod
    def _score_text(text: str, query: str, keywords: List[str]) -> int:
        if not text:
            return 0
        text_lower = text.lower()
        score = 0
        if query.lower() in text_lower:
            score += 100
        for keyword in keywords:
            if keyword in text_lower:
                score += 10
        return score

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        data = self._load_graph_data(graph_id)
        nodes = []
        for node in data.get("nodes", []):
            nodes.append(
                NodeInfo(
                    uuid=node.get("uuid", ""),
                    name=node.get("name", ""),
                    labels=node.get("labels", []) or [],
                    summary=node.get("summary", "") or "",
                    attributes=node.get("attributes", {}) or {},
                )
            )
        logger.info("노드 %s개를 가져왔습니다", len(nodes))
        return nodes

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        data = self._load_graph_data(graph_id)
        node_map = self._build_node_map(graph_id)
        edges = []
        for edge in data.get("edges", []):
            source_uuid = edge.get("source_node_uuid", "")
            target_uuid = edge.get("target_node_uuid", "")
            source_name = edge.get("source_node_name") or node_map.get(source_uuid, {}).get("name")
            target_name = edge.get("target_node_name") or node_map.get(target_uuid, {}).get("name")
            item = EdgeInfo(
                uuid=edge.get("uuid", ""),
                name=edge.get("name", "") or "",
                fact=edge.get("fact", "") or "",
                source_node_uuid=source_uuid,
                target_node_uuid=target_uuid,
                source_node_name=source_name,
                target_node_name=target_name,
                attributes=edge.get("attributes", {}) or {},
                episodes=edge.get("episodes", []) or [],
            )
            if include_temporal:
                item.created_at = edge.get("created_at")
                item.valid_at = edge.get("valid_at")
                item.invalid_at = edge.get("invalid_at")
                item.expired_at = edge.get("expired_at")
            edges.append(item)
        logger.info("엣지 %s개를 가져왔습니다", len(edges))
        return edges

    def get_node_detail(self, graph_id: str, node_uuid: str) -> Optional[NodeInfo]:
        for node in self.get_all_nodes(graph_id):
            if node.uuid == node_uuid:
                return node
        return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        return [
            edge
            for edge in self.get_all_edges(graph_id)
            if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid
        ]

    def search_graph(self, graph_id: str, query: str, limit: int = 10, scope: str = "edges") -> SearchResult:
        logger.info("로컬 그래프 검색: graph_id=%s, query=%s, scope=%s", graph_id, query[:50], scope)
        keywords = self._tokenize(query)
        facts: List[str] = []
        edge_results: List[Dict[str, Any]] = []
        node_results: List[Dict[str, Any]] = []

        if scope in ["edges", "both"]:
            scored_edges = []
            for edge in self.get_all_edges(graph_id):
                source = edge.source_node_name or ""
                target = edge.target_node_name or ""
                searchable = " ".join([edge.name, edge.fact, source, target, json.dumps(edge.attributes, ensure_ascii=False)])
                score = self._score_text(searchable, query, keywords)
                if score > 0:
                    scored_edges.append((score, edge))
            scored_edges.sort(key=lambda item: item[0], reverse=True)
            for _, edge in scored_edges[:limit]:
                if edge.fact:
                    facts.append(edge.fact)
                edge_results.append(edge.to_dict())

        if scope in ["nodes", "both"]:
            scored_nodes = []
            for node in self.get_all_nodes(graph_id):
                searchable = " ".join(
                    [
                        node.name,
                        node.summary,
                        " ".join(node.labels),
                        json.dumps(node.attributes, ensure_ascii=False),
                    ]
                )
                score = self._score_text(searchable, query, keywords)
                if score > 0:
                    scored_nodes.append((score, node))
            scored_nodes.sort(key=lambda item: item[0], reverse=True)
            for _, node in scored_nodes[:limit]:
                node_results.append(node.to_dict())
                if node.summary:
                    facts.append(f"[{node.name}]: {node.summary}")

        return SearchResult(
            facts=facts,
            edges=edge_results,
            nodes=node_results,
            query=query,
            total_count=len(facts),
        )

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[NodeInfo]:
        return [node for node in self.get_all_nodes(graph_id) if entity_type in node.labels]

    def get_entity_summary(self, graph_id: str, entity_name: str) -> Dict[str, Any]:
        search_result = self.search_graph(graph_id=graph_id, query=entity_name, limit=20, scope="both")
        entity_node = next((node for node in self.get_all_nodes(graph_id) if node.name.lower() == entity_name.lower()), None)
        related_edges = self.get_node_edges(graph_id, entity_node.uuid) if entity_node else []
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [edge.to_dict() for edge in related_edges],
            "total_relations": len(related_edges),
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        entity_types: Dict[str, int] = {}
        relation_types: Dict[str, int] = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }

    def get_simulation_context(self, graph_id: str, simulation_requirement: str, limit: int = 30) -> Dict[str, Any]:
        search_result = self.search_graph(graph_id=graph_id, query=simulation_requirement, limit=limit, scope="both")
        stats = self.get_graph_statistics(graph_id)
        entities = []
        for node in self.get_all_nodes(graph_id):
            custom_labels = [label for label in node.labels if label not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({"name": node.name, "type": custom_labels[0], "summary": node.summary})
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],
            "total_entities": len(entities),
        }

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5,
    ) -> InsightForgeResult:
        result = InsightForgeResult(query=query, simulation_requirement=simulation_requirement, sub_queries=[])
        result.sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries,
        )

        all_facts: List[str] = []
        all_edges: List[Dict[str, Any]] = []
        seen_facts = set()

        for sub_query in result.sub_queries:
            search_result = self.search_graph(graph_id=graph_id, query=sub_query, limit=15, scope="edges")
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            all_edges.extend(search_result.edges)

        main_search = self.search_graph(graph_id=graph_id, query=query, limit=20, scope="edges")
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        entity_uuids = set()
        for edge in all_edges:
            if edge.get("source_node_uuid"):
                entity_uuids.add(edge["source_node_uuid"])
            if edge.get("target_node_uuid"):
                entity_uuids.add(edge["target_node_uuid"])

        entity_insights = []
        node_map: Dict[str, NodeInfo] = {}
        for node_uuid in entity_uuids:
            node = self.get_node_detail(graph_id, node_uuid)
            if not node:
                continue
            node_map[node_uuid] = node
            entity_type = next((label for label in node.labels if label not in ["Entity", "Node"]), "엔티티")
            related_facts = [fact for fact in all_facts if node.name.lower() in fact.lower()]
            entity_insights.append(
                {
                    "uuid": node.uuid,
                    "name": node.name,
                    "type": entity_type,
                    "summary": node.summary,
                    "related_facts": related_facts,
                }
            )
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        relationship_chains = []
        for edge in all_edges:
            source_uuid = edge.get("source_node_uuid", "")
            target_uuid = edge.get("target_node_uuid", "")
            source_name = node_map.get(source_uuid, NodeInfo("", "", [], "", {})).name or source_uuid[:8]
            target_name = node_map.get(target_uuid, NodeInfo("", "", [], "", {})).name or target_uuid[:8]
            chain = f"{source_name} --[{edge.get('name', '')}]--> {target_name}"
            if chain not in relationship_chains:
                relationship_chains.append(chain)
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        return result

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5,
    ) -> List[str]:
        system_prompt = """당신은 전문 문제 분석 전문가입니다. 복잡한 질문을 여러 개의 검색 가능한 하위 질문으로 나누고 JSON: {"sub_queries": [...]} 형식으로 반환하세요."""
        user_prompt = f"""시뮬레이션 요구 배경:\n{simulation_requirement}\n\n보고서 맥락:\n{report_context[:500]}\n\n이 질문을 최대 {max_queries}개의 하위 질문으로 나누세요:\n{query}"""
        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            sub_queries = response.get("sub_queries", [])
            return [str(item) for item in sub_queries[:max_queries]]
        except Exception as error:
            logger.warning("하위 질문 생성에 실패해 기본 분할을 사용합니다: %s", error)
            return [query, f"{query}의 주요 참여자", f"{query}의 원인과 영향", f"{query}의 전개 과정"][:max_queries]

    def panorama_search(self, graph_id: str, query: str, include_expired: bool = True, limit: int = 50) -> PanoramaResult:
        result = PanoramaResult(query=query)
        result.all_nodes = self.get_all_nodes(graph_id)
        result.total_nodes = len(result.all_nodes)
        result.all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.total_edges = len(result.all_edges)

        active_facts: List[str] = []
        historical_facts: List[str] = []
        for edge in result.all_edges:
            if not edge.fact:
                continue
            if edge.is_expired or edge.is_invalid:
                valid_at = edge.valid_at or "미상"
                invalid_at = edge.invalid_at or edge.expired_at or "미상"
                historical_facts.append(f"[{valid_at} - {invalid_at}] {edge.fact}")
            else:
                active_facts.append(edge.fact)

        query_lower = query.lower()
        keywords = self._tokenize(query)

        def score(fact: str) -> int:
            return self._score_text(fact.lower(), query_lower, keywords)

        active_facts.sort(key=score, reverse=True)
        historical_facts.sort(key=score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        return result

    def quick_search(self, graph_id: str, query: str, limit: int = 10) -> SearchResult:
        return self.search_graph(graph_id=graph_id, query=query, limit=limit, scope="edges")

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: Optional[List[str]] = None,
    ) -> InterviewResult:
        from .simulation_runner import SimulationRunner

        result = InterviewResult(interview_topic=interview_requirement, interview_questions=custom_questions or [])
        profiles = self._load_agent_profiles(simulation_id)
        if not profiles:
            result.summary = "인터뷰할 수 있는 에이전트 인물 설정 파일을 찾지 못했습니다"
            return result

        result.total_agents = len(profiles)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents,
        )
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning

        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents,
            )

        combined_prompt = "\n".join([f"{index + 1}. {question}" for index, question in enumerate(result.interview_questions)])
        optimized_prompt = (
            "지금 당신은 인터뷰를 받고 있습니다. 자신의 인물 설정, 모든 과거 기억과 행동을 바탕으로 아래 질문에 순수 텍스트로 직접 답변하세요.\n"
            "어떤 도구도 호출하지 말고, JSON을 반환하지 말며, Markdown 제목도 사용하지 마세요.\n\n"
            f"{combined_prompt}"
        )

        try:
            interviews_request = [{"agent_id": agent_idx, "prompt": optimized_prompt} for agent_idx in selected_indices]
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,
                timeout=180.0,
            )

            if not api_result.get("success", False):
                result.summary = f"인터뷰 API 호출에 실패했습니다: {api_result.get('error', '알 수 없는 오류')}."
                return result

            results_dict = api_result.get("result", {}).get("results", {})
            for position, agent_idx in enumerate(selected_indices):
                agent = selected_agents[position]
                agent_name = agent.get("realname", agent.get("username", f"에이전트_{agent_idx}"))
                agent_role = agent.get("profession", "미상")
                agent_bio = agent.get("bio", "")

                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                twitter_response = self._clean_tool_call_response(twitter_result.get("response", ""))
                reddit_response = self._clean_tool_call_response(reddit_result.get("response", ""))
                response_text = (
                    "【트위터 플랫폼 답변】\n"
                    f"{twitter_response or '(해당 플랫폼에서 응답을 받지 못했습니다)'}\n\n"
                    "【레딧 플랫폼 답변】\n"
                    f"{reddit_response or '(해당 플랫폼에서 응답을 받지 못했습니다)'}"
                )

                combined_responses = f"{twitter_response} {reddit_response}"
                sentences = re.split(r"[。！？]", combined_responses)
                meaningful = [text.strip() for text in sentences if 20 <= len(text.strip()) <= 150]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [text + "。" for text in meaningful[:3]]

                result.interviews.append(
                    AgentInterview(
                        agent_name=agent_name,
                        agent_role=agent_role,
                        agent_bio=agent_bio[:1000],
                        question=combined_prompt,
                        response=response_text,
                        key_quotes=key_quotes[:5],
                    )
                )

            result.interviewed_count = len(result.interviews)
        except ValueError as error:
            result.summary = f"인터뷰에 실패했습니다: {error}. 시뮬레이션 환경이 종료되었을 수 있습니다."
            return result
        except Exception as error:
            logger.error("인터뷰 과정에서 오류가 발생했습니다: %s", error)
            result.summary = f"인터뷰 과정에서 오류가 발생했습니다: {error}"
            return result

        if result.interviews:
            result.summary = self._generate_interview_summary(result.interviews, interview_requirement)
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        if not response or not response.strip().startswith("{"):
            return response
        text = response.strip()
        if "tool_name" not in text[:80]:
            return response
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "arguments" in data:
                for key in ("content", "text", "body", "message", "reply"):
                    if key in data["arguments"]:
                        return str(data["arguments"][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace("\\n", "\n").replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        sim_dir = os.path.join(os.path.dirname(__file__), f"../../uploads/simulations/{simulation_id}")
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")

        if os.path.exists(reddit_profile_path):
            with open(reddit_profile_path, "r", encoding="utf-8") as file:
                return json.load(file)

        profiles: List[Dict[str, Any]] = []
        if os.path.exists(twitter_profile_path):
            with open(twitter_profile_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    profiles.append(
                        {
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "미상",
                        }
                    )
        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int,
    ) -> tuple:
        summaries = []
        for index, profile in enumerate(profiles):
            summaries.append(
                {
                    "index": index,
                    "name": profile.get("realname", profile.get("username", f"에이전트_{index}")),
                    "profession": profile.get("profession", "미상"),
                    "bio": profile.get("bio", "")[:200],
                    "interested_topics": profile.get("interested_topics", []),
                }
            )

        system_prompt = """당신은 인터뷰 기획 전문가입니다. 인터뷰 요구에 따라 후보 에이전트 중 가장 인터뷰할 가치가 높은 대상을 선택하고 JSON: {"selected_indices": [...], "reasoning": "..."} 형식으로 반환하세요."""
        user_prompt = f"""인터뷰 요구사항: {interview_requirement}\n\n시뮬레이션 배경: {simulation_requirement or '제공되지 않음'}\n\n후보 에이전트:\n{json.dumps(summaries, ensure_ascii=False, indent=2)}"""
        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            selected_indices = [index for index in response.get("selected_indices", []) if 0 <= index < len(profiles)]
            selected_indices = selected_indices[:max_agents]
            selected_agents = [profiles[index] for index in selected_indices]
            return selected_agents, selected_indices, response.get("reasoning", "관련성을 기준으로 자동 선택")
        except Exception as error:
            logger.warning("인터뷰 대상을 선택하지 못해 기본 전략을 사용합니다: %s", error)
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "기본 선택 전략을 사용했습니다"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]],
    ) -> List[str]:
        roles = [agent.get("profession", "미상") for agent in selected_agents]
        system_prompt = """당신은 인터뷰 기자입니다. 인터뷰 요구를 바탕으로 3~5개의 개방형 질문을 생성하고 JSON: {"questions": [...]} 형식으로 반환하세요."""
        user_prompt = f"""인터뷰 요구사항: {interview_requirement}\n\n시뮬레이션 배경: {simulation_requirement or '제공되지 않음'}\n\n인터뷰 대상 역할: {', '.join(roles)}"""
        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
            )
            questions = response.get("questions", [])
            return questions or [f"{interview_requirement}에 대해 어떻게 생각하십니까?"]
        except Exception as error:
            logger.warning("인터뷰 질문 생성에 실패해 기본 질문을 사용합니다: %s", error)
            return [
                f"{interview_requirement}에 대한 귀하의 의견은 무엇입니까?",
                "이 일이 귀하 또는 귀하가 대표하는 집단에 어떤 영향을 미칩니까?",
                "이 문제를 어떻게 해결하거나 개선할 수 있다고 생각하십니까?",
            ]

    def _generate_interview_summary(self, interviews: List[AgentInterview], interview_requirement: str) -> str:
        interview_texts = [f"【{item.agent_name}({item.agent_role})】\n{item.response[:500]}" for item in interviews]
        system_prompt = """당신은 뉴스 편집자입니다. 인터뷰 내용을 바탕으로 객관적이고 중립적인 인터뷰 요약을 순수 텍스트 문단으로 작성하세요."""
        user_prompt = f"""인터뷰 주제: {interview_requirement}\n\n인터뷰 내용:\n{''.join(interview_texts)}"""
        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            if not summary or not summary.strip():
                raise ValueError("LLM이 빈 요약을 반환했습니다")
            return summary
        except Exception as error:
            logger.warning("인터뷰 요약 생성에 실패해 대체 요약을 사용합니다: %s", error)
            return f"총 {len(interviews)}명의 응답자를 인터뷰했습니다: " + "、".join([item.agent_name for item in interviews])
