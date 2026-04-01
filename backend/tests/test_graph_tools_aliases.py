import json

from app.config import Config
from app.services.graph_tools import GraphToolsService
from app.services.simulation_runner import SimulationRunner


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
                    "name": "Korea University",
                    "aliases": ["고려대학교", "高麗大學校"],
                    "labels": ["Entity", "Organization"],
                    "summary": "대한민국 서울의 주요 대학",
                    "attributes": {},
                }
            ],
            "edges": [],
        },
    )

    service = GraphToolsService()
    result = service.get_entity_summary(graph_id, "고려대학교")

    assert result["entity_info"] is not None
    assert result["entity_info"]["name"] == "Korea University"
    assert set(result["entity_info"]["aliases"]) == {"고려대학교", "高麗大學校"}


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
                    "fact": "고려대학교는 사건에 대응했다",
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


def test_interview_agents_falls_back_to_single_interviews_after_batch_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(Config, "REPORT_INTERVIEW_BATCH_SIZE", 2)
    monkeypatch.setattr(Config, "REPORT_INTERVIEW_BASE_TIMEOUT", 180.0)
    monkeypatch.setattr(Config, "REPORT_INTERVIEW_PER_AGENT_TIMEOUT", 90.0)
    monkeypatch.setattr(Config, "REPORT_INTERVIEW_PER_PLATFORM_TIMEOUT", 60.0)
    monkeypatch.setattr(Config, "REPORT_INTERVIEW_MAX_TIMEOUT", 900.0)

    sim_dir = tmp_path / "simulations" / "sim-test"
    sim_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "env_status.json").write_text(
        json.dumps({"status": "alive", "twitter_available": True, "reddit_available": True}),
        encoding="utf-8",
    )

    service = GraphToolsService()
    profiles = [
        {"realname": "에이전트 A", "profession": "분석가", "bio": "A"},
        {"realname": "에이전트 B", "profession": "투자자", "bio": "B"},
        {"realname": "에이전트 C", "profession": "기자", "bio": "C"},
    ]
    monkeypatch.setattr(service, "_load_agent_profiles", lambda simulation_id: profiles)
    monkeypatch.setattr(
        service,
        "_select_agents_for_interview",
        lambda profiles, interview_requirement, simulation_requirement, max_agents: (
            profiles[:3],
            [0, 1, 2],
            "관련도가 높은 인물을 선택했습니다",
        ),
    )
    monkeypatch.setattr(
        service,
        "_generate_interview_questions",
        lambda interview_requirement, simulation_requirement, selected_agents: ["전망을 어떻게 보십니까?"],
    )
    monkeypatch.setattr(service, "_generate_interview_summary", lambda interviews, interview_requirement: "요약 완료")

    batch_timeouts = []
    batch_calls = []
    single_timeouts = []
    single_calls = []

    def fake_batch(cls, simulation_id, interviews, platform=None, timeout=0):
        batch_calls.append([item["agent_id"] for item in interviews])
        batch_timeouts.append(timeout)
        if len(interviews) > 1:
            return {"success": False, "error": "Request timed out."}
        agent_id = interviews[0]["agent_id"]
        return {
            "success": True,
            "result": {
                "results": {
                    f"twitter_{agent_id}": {"response": f"twitter-{agent_id}"},
                    f"reddit_{agent_id}": {"response": f"reddit-{agent_id}"},
                }
            },
        }

    def fake_single(cls, simulation_id, agent_id, prompt, platform=None, timeout=0):
        single_calls.append(agent_id)
        single_timeouts.append(timeout)
        return {
            "success": True,
            "result": {
                "agent_id": agent_id,
                "prompt": prompt,
                "platforms": {
                    "twitter": {"response": f"twitter-{agent_id}"},
                    "reddit": {"response": f"reddit-{agent_id}"},
                },
            },
        }

    monkeypatch.setattr(SimulationRunner, "interview_agents_batch", classmethod(fake_batch))
    monkeypatch.setattr(SimulationRunner, "interview_agent", classmethod(fake_single))

    result = service.interview_agents(
        simulation_id="sim-test",
        interview_requirement="삼성전자 전망",
        simulation_requirement="한 달 뒤 주가",
        max_agents=3,
    )

    assert batch_calls == [[0, 1]]
    assert batch_timeouts == [330.0]
    assert single_calls == [0, 1, 2]
    assert single_timeouts == [240.0, 240.0, 240.0]
    assert result.interviewed_count == 3
    assert [item.agent_name for item in result.interviews] == ["에이전트 A", "에이전트 B", "에이전트 C"]
    assert result.summary == "요약 완료"


def test_load_agent_profiles_skips_full_profile_localization(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))

    sim_dir = tmp_path / "simulations" / "sim-test"
    sim_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps([{"realname": "테스트", "bio": "漢字 bio"}], ensure_ascii=False),
        encoding="utf-8",
    )

    service = GraphToolsService()
    calls = []

    def fake_adapt(profiles, platform="reddit"):
        calls.append((platform, len(profiles)))
        return [{"realname": "테스트", "bio": "漢字 bio"}]

    def fail_localize(*args, **kwargs):
        raise AssertionError("전체 프로필 현지화는 호출되면 안 됩니다")

    monkeypatch.setattr(service.profile_localizer, "adapt_profiles", fake_adapt)
    monkeypatch.setattr(service.profile_localizer, "adapt_and_localize_profiles", fail_localize)

    result = service._load_agent_profiles("sim-test")

    assert calls == [("reddit", 1)]
    assert result == [{"realname": "테스트", "bio": "漢字 bio"}]
