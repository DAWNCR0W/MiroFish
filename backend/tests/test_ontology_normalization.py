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
                "examples": "\u6768\u666f\u5a9b",
            },
            {
                "name": "Professor",
                "description": "A professor",
                "attributes": "name",
                "examples": ["\u4e25\u6b22\u6559\u6388"],
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
    assert normalized["entity_types"][0]["examples"] == ["\u6768\u666f\u5a9b"]
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


def test_normalize_ontology_parses_stringified_json_fields():
    raw = {
        "entity_types": [
            {
                "name": "ETF",
                "description": "ETF instrument",
                "attributes": '[{"name":"ticker_symbol","type":"text","description":"Ticker"},{"name":"strategy_type","type":"text","description":"Strategy"}]',
                "examples": '["JEPI","VOO"]',
            }
        ],
        "edge_types": [
            {
                "name": "ISSUES",
                "description": "Issues an ETF",
                "source_targets": '[{"source":"ETFIssuer","target":"ETF"}]',
                "attributes": '[{"name":"confidence","type":"text","description":"Confidence"}]',
            }
        ],
        "analysis_summary": "요약",
    }

    normalized = normalize_ontology(raw)

    assert normalized["entity_types"][0]["attributes"] == [
        {
            "name": "ticker_symbol",
            "type": "text",
            "description": "Ticker",
        },
        {
            "name": "strategy_type",
            "type": "text",
            "description": "Strategy",
        },
    ]
    assert normalized["entity_types"][0]["examples"] == ["JEPI", "VOO"]
    assert normalized["edge_types"][0]["source_targets"] == [
        {"source": "ETFIssuer", "target": "ETF"}
    ]
    assert normalized["edge_types"][0]["attributes"] == [
        {
            "name": "confidence",
            "type": "text",
            "description": "Confidence",
        }
    ]


def test_normalize_ontology_recovers_previously_misnormalized_fields():
    raw = {
        "entity_types": [
            {
                "name": "ETF",
                "description": "ETF instrument",
                "attributes": [
                    {
                        "name": '[{"name":"ticker_symbol","type":"text","description":"Ticker"}]',
                        "type": "text",
                        "description": '[{"name":"ticker_symbol","type":"text","description":"Ticker"}]',
                    }
                ],
                "examples": ['["JEPI","VOO"]'],
            }
        ],
        "edge_types": [],
        "analysis_summary": "요약",
    }

    normalized = normalize_ontology(raw)

    assert normalized["entity_types"][0]["attributes"] == [
        {
            "name": "ticker_symbol",
            "type": "text",
            "description": "Ticker",
        }
    ]
    assert normalized["entity_types"][0]["examples"] == ["JEPI", "VOO"]


def test_normalize_ontology_recovers_project_style_attribute_blob():
    raw = {
        "entity_types": [
            {
                "name": "IndividualInvestor",
                "description": "Retail investor persona",
                "attributes": [
                    {
                        "name": '[{"name": "user_handle", "type": "text", "description": "Social media username or handle"}, {"name": "investment_focus", "type": "text", "description": "Primary investment goal"}]',
                        "type": "text",
                        "description": '[{"name": "user_handle", "type": "text", "description": "Social media username or handle"}, {"name": "investment_focus", "type": "text", "description": "Primary investment goal"}]',
                    }
                ],
                "examples": [],
            }
        ],
        "edge_types": [],
        "analysis_summary": "요약",
    }

    normalized = normalize_ontology(raw)

    assert normalized["entity_types"][0]["attributes"] == [
        {
            "name": "user_handle",
            "type": "text",
            "description": "Social media username or handle",
        },
        {
            "name": "investment_focus",
            "type": "text",
            "description": "Primary investment goal",
        },
    ]


def test_local_graph_extractor_accepts_malformed_ontology():
    malformed_ontology = {
        "entity_types": [
            {
                "name": "Student",
                "description": "A student",
                "attributes": 2,
                "examples": "\u6768\u666f\u5a9b",
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


def test_local_graph_extractor_coerces_stringified_attribute_maps():
    class JsonishLLMClient:
        def chat_json(self, messages, temperature=None, max_tokens=None):
            return {
                "entities": [
                    {
                        "name": "JEPI",
                        "type": "ETF",
                        "aliases": '["JPMorgan Equity Premium Income ETF"]',
                        "summary": "월배당 ETF",
                        "attributes": '{"ticker_symbol":"JEPI","strategy_type":"covered call","ignored":"x"}',
                    },
                    {
                        "name": "JPMorgan Chase & Co.",
                        "type": "ETFIssuer",
                        "summary": "발행사",
                        "attributes": "company_name=JPMorgan",
                    },
                ],
                "relationships": [
                    {
                        "type": "ISSUES",
                        "source_name": "JPMorgan Chase & Co.",
                        "source_type": "ETFIssuer",
                        "target_name": "JEPI",
                        "target_type": "ETF",
                        "fact": "JPMorgan Chase & Co. issues JEPI.",
                        "attributes": '[{"confidence":"high"}]',
                    }
                ],
                "summary": "정상 처리",
            }

    ontology = {
        "entity_types": [
            {
                "name": "ETF",
                "description": "ETF instrument",
                "attributes": [
                    {"name": "ticker_symbol", "type": "text", "description": "Ticker"},
                    {"name": "strategy_type", "type": "text", "description": "Strategy"},
                ],
                "examples": ["JEPI"],
            },
            {
                "name": "ETFIssuer",
                "description": "ETF issuer",
                "attributes": [
                    {"name": "company_name", "type": "text", "description": "Company name"},
                ],
                "examples": ["JPMorgan Chase & Co."],
            },
        ],
        "edge_types": [
            {
                "name": "ISSUES",
                "description": "Issues an ETF",
                "source_targets": [{"source": "ETFIssuer", "target": "ETF"}],
                "attributes": [
                    {"name": "confidence", "type": "text", "description": "Confidence"},
                ],
            }
        ],
    }

    extractor = LocalGraphExtractor(llm_client=JsonishLLMClient())
    result = extractor.extract("테스트 텍스트", ontology)

    assert result["entities"] == [
        {
            "name": "JEPI",
            "type": "ETF",
            "aliases": ["JPMorgan Equity Premium Income ETF"],
            "summary": "월배당 ETF",
            "attributes": {
                "ticker_symbol": "JEPI",
                "strategy_type": "covered call",
            },
        },
        {
            "name": "JPMorgan Chase & Co.",
            "type": "ETFIssuer",
            "aliases": [],
            "summary": "발행사",
            "attributes": {},
        },
    ]
    assert result["relationships"] == [
        {
            "type": "ISSUES",
            "source_name": "JPMorgan Chase & Co.",
            "source_type": "ETFIssuer",
            "target_name": "JEPI",
            "target_type": "ETF",
            "fact": "JPMorgan Chase & Co. issues JEPI.",
            "attributes": {"confidence": "high"},
        }
    ]
    assert result["summary"] == "정상 처리"


def test_ontology_generator_adds_fallback_edge_types_when_empty():
    generator = OntologyGenerator(llm_client=DummyLLMClient())

    processed = generator._validate_and_process(
        {
            "entity_types": [
                {
                    "name": "Student",
                    "description": "A student",
                    "attributes": "full_name",
                    "examples": "\u6768\u666f\u5a9b",
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
