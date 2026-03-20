from app.services.report_agent import (
    Report,
    ReportAgent,
    ReportManager,
    ReportOutline,
    ReportSection,
    ReportStatus,
)


class DummyOutlineLLM:
    def __init__(self, response):
        self.response = response

    def chat_json(self, messages, temperature=None, max_tokens=None):
        return self.response


class DummyGraphTools:
    def get_simulation_context(self, graph_id, simulation_requirement, limit=30):
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": [],
            "graph_statistics": {
                "graph_id": graph_id,
                "total_nodes": 11,
                "total_edges": 0,
                "entity_types": {
                    "Person": 6,
                    "Organization": 5,
                },
            },
            "entities": [
                {"name": "武汉大学", "type": "Organization", "summary": "브랜드 평판 위기를 겪는 대학"},
                {"name": "辛某", "type": "Person", "summary": "사건의 핵심 당사자"},
            ],
            "total_entities": 11,
        }


def test_plan_outline_falls_back_when_llm_returns_empty_sections():
    agent = ReportAgent(
        graph_id="graph_test",
        simulation_id="sim_test",
        simulation_requirement="우한대학 공고 이후 여론 반응 예측",
        llm_client=DummyOutlineLLM({
            "title": "빈 개요",
            "summary": "",
            "sections": [],
        }),
        graph_tools=DummyGraphTools(),
    )

    outline = agent.plan_outline()

    assert outline.title == "시뮬레이션 분석 보고서"
    assert len(outline.sections) == 3
    assert outline.summary


def test_report_manager_prefers_renderable_completed_report(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))

    empty_report = Report(
        report_id="report_empty",
        simulation_id="sim_same",
        graph_id="graph_test",
        simulation_requirement="테스트 요구사항",
        status=ReportStatus.COMPLETED,
        outline=ReportOutline(
            title="시뮬레이션 분석 보고서",
            summary="",
            sections=[],
        ),
        markdown_content="# 시뮬레이션 분석 보고서\n\n> \n\n---\n\n",
        created_at="2026-03-21T03:00:00",
        completed_at="2026-03-21T03:00:05",
    )
    valid_report = Report(
        report_id="report_valid",
        simulation_id="sim_same",
        graph_id="graph_test",
        simulation_requirement="테스트 요구사항",
        status=ReportStatus.COMPLETED,
        outline=ReportOutline(
            title="시뮬레이션 분석 보고서",
            summary="핵심 추세 요약",
            sections=[ReportSection(title="핵심 발견")],
        ),
        markdown_content="# 시뮬레이션 분석 보고서\n\n## 핵심 발견\n\n실제 본문 내용이 있습니다.\n",
        created_at="2026-03-21T02:00:00",
        completed_at="2026-03-21T02:00:05",
    )

    ReportManager.save_report(empty_report)
    ReportManager.save_report(valid_report)

    assert ReportManager.is_report_renderable(empty_report) is False
    assert ReportManager.is_report_renderable(valid_report) is True

    selected = ReportManager.get_report_by_simulation("sim_same")

    assert selected is not None
    assert selected.report_id == "report_valid"
