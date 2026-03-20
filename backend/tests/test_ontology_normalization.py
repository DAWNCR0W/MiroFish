from app.services.local_graph_extractor import LocalGraphExtractor
from app.services.ontology_generator import FALLBACK_EDGE_TYPES, OntologyGenerator
from app.utils.ontology import normalize_ontology


class DummyLLMClient:
    def chat_json(self, messages, temperature=None, max_tokens=None):
        return {
            "entities": [],
            "relationships": [],
            "summary": "정상 처리",
        }


def test_normalize_ontology_handles_malformed_fields():
    raw = {
        "entity_types": [
            {
                "name": "Student",
                "description": "A student",
                "attributes": 2,
                "examples": "杨景媛",
            },
            {
                "name": "Professor",
                "description": "A professor",
                "attributes": "name",
                "examples": ["严欢教授"],
            },
        ],
        "edge_types": [
            {
                "name": "STUDIES_AT",
                "description": "Studies at",
                "source_targets": "source: Student, target: University",
                "attributes": ["enrollment_year"],
            }
        ],
        "analysis_summary": "요약",
    }

    normalized = normalize_ontology(raw)

    assert normalized["entity_types"][0]["attributes"] == []
    assert normalized["entity_types"][0]["examples"] == ["杨景媛"]
    assert normalized["entity_types"][1]["attributes"] == []
    assert normalized["edge_types"][0]["source_targets"] == [
        {"source": "Student", "target": "University"}
    ]
    assert normalized["edge_types"][0]["attributes"] == [
        {
            "name": "enrollment_year",
            "type": "text",
            "description": "enrollment_year",
        }
    ]


def test_local_graph_extractor_accepts_malformed_ontology():
    malformed_ontology = {
        "entity_types": [
            {
                "name": "Student",
                "description": "A student",
                "attributes": 2,
                "examples": "杨景媛",
            }
        ],
        "edge_types": [
            {
                "name": "STUDIES_AT",
                "description": "Studies at",
                "source_targets": "source: Student, target: University",
                "attributes": [],
            }
        ],
    }

    extractor = LocalGraphExtractor(llm_client=DummyLLMClient())
    result = extractor.extract("테스트 텍스트", malformed_ontology)

    assert result == {
        "entities": [],
        "relationships": [],
        "summary": "정상 처리",
    }


def test_ontology_generator_adds_fallback_edge_types_when_empty():
    generator = OntologyGenerator(llm_client=DummyLLMClient())

    processed = generator._validate_and_process(
        {
            "entity_types": [
                {
                    "name": "Student",
                    "description": "A student",
                    "attributes": "full_name",
                    "examples": "杨景媛",
                }
            ],
            "edge_types": [],
            "analysis_summary": "",
        }
    )

    assert len(processed["edge_types"]) == len(FALLBACK_EDGE_TYPES)
    assert [edge["name"] for edge in processed["edge_types"]] == [
        edge["name"] for edge in FALLBACK_EDGE_TYPES
    ]
    assert processed["edge_types"][0]["source_targets"] == [
        {"source": "Person", "target": "Organization"},
        {"source": "Organization", "target": "Organization"},
    ]
    assert any(entity["name"] == "Person" for entity in processed["entity_types"])
    assert any(entity["name"] == "Organization" for entity in processed["entity_types"])
