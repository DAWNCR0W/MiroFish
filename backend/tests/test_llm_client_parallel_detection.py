from app.utils.llm_client import LLMClient


def test_detect_parallel_from_lmstudio_api_v1_payload(monkeypatch):
    payload = {
        "models": [
            {
                "key": "zai-org/glm-4.7-flash",
                "loaded_instances": [
                    {
                        "id": "zai-org/glm-4.7-flash",
                        "config": {
                            "context_length": 202752,
                            "parallel": 8,
                        },
                    }
                ],
            }
        ]
    }

    monkeypatch.setattr(
        LLMClient,
        "_fetch_json",
        classmethod(lambda cls, url, api_key=None, timeout=3: payload),
    )
    monkeypatch.setattr(
        LLMClient,
        "_parallel_cache",
        {},
    )

    workers, source = LLMClient.get_recommended_parallel_requests_with_source(
        api_key="token",
        base_url="http://localhost:1234/v1",
        model="zai-org/glm-4.7-flash",
        fallback=3,
        max_cap=16,
    )

    assert workers == 8
    assert source == "server_capability"


def test_detect_parallel_respects_cap(monkeypatch):
    payload = {
        "models": [
            {
                "key": "zai-org/glm-4.7-flash",
                "loaded_instances": [
                    {
                        "id": "zai-org/glm-4.7-flash",
                        "config": {"parallel": 32},
                    }
                ],
            }
        ]
    }

    monkeypatch.setattr(
        LLMClient,
        "_fetch_json",
        classmethod(lambda cls, url, api_key=None, timeout=3: payload),
    )
    monkeypatch.setattr(
        LLMClient,
        "_parallel_cache",
        {},
    )

    workers = LLMClient.get_recommended_parallel_requests(
        api_key="token",
        base_url="http://localhost:1234/v1",
        model="zai-org/glm-4.7-flash",
        fallback=3,
        max_cap=12,
    )

    assert workers == 12


def test_detect_parallel_falls_back_when_metadata_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        LLMClient,
        "_fetch_json",
        classmethod(lambda cls, url, api_key=None, timeout=3: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    monkeypatch.setattr(
        LLMClient,
        "_parallel_cache",
        {},
    )

    workers, source = LLMClient.get_recommended_parallel_requests_with_source(
        api_key="token",
        base_url="http://localhost:1234/v1",
        model="zai-org/glm-4.7-flash",
        fallback=5,
        max_cap=16,
    )

    assert workers == 5
    assert source == "config_fallback"


def test_manual_override_takes_precedence_over_detection(monkeypatch):
    payload = {
        "models": [
            {
                "key": "zai-org/glm-4.7-flash",
                "loaded_instances": [
                    {
                        "id": "zai-org/glm-4.7-flash",
                        "config": {"parallel": 8},
                    }
                ],
            }
        ]
    }

    monkeypatch.setattr(
        LLMClient,
        "_fetch_json",
        classmethod(lambda cls, url, api_key=None, timeout=3: payload),
    )
    monkeypatch.setattr(
        LLMClient,
        "_parallel_cache",
        {},
    )

    client = LLMClient(
        api_key="token",
        base_url="http://localhost:1234/v1",
        model="zai-org/glm-4.7-flash",
        max_parallel_requests=6,
    )

    assert client.get_max_parallel_requests(max_cap=16) == 6


def test_candidate_model_metadata_endpoints_include_v1_models():
    endpoints = LLMClient._candidate_model_metadata_endpoints("http://localhost:1234/v1")

    assert "http://localhost:1234/v1/models" in endpoints
