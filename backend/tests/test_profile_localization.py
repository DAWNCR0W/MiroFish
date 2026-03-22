import json
from types import SimpleNamespace

import app.services.profile_localization as profile_localization_module
from app.services.oasis_profile_generator import OasisProfileGenerator
from app.services.profile_localization import ProfileLocalizationService


def test_profile_localizer_normalizes_common_scalar_fields():
    service = ProfileLocalizationService(api_key="")

    result = service.localize_profile({
        "country": "US",
        "profession": "student",
        "interested_topics": ["General", "Social Issues", "Technology"],
    })

    assert result["country"] == "미국"
    assert result["profession"] == "학생"
    assert result["interested_topics"] == ["일반", "사회 이슈", "기술"]


def test_profile_localizer_translates_ideograph_fields_with_batch_translator(monkeypatch):
    service = ProfileLocalizationService(api_key="")
    service.client = object()

    def fake_translate(payloads):
        assert len(payloads) == 1
        return [
            {
                "bio": "원문 소개의 한국어 번역",
                "persona": "원문 페르소나의 한국어 번역",
                "profession": "시장 분석가",
                "country": "일본",
                "interested_topics": ["시장 분석", "ETF"],
            }
        ]

    monkeypatch.setattr(service, "_translate_batch", fake_translate)

    result = service.localize_profiles([
        {
            "bio": "\u65e5\u672c\u5e02\u5834\u3068ETF\u3092\u4e2d\u5fc3\u306b\u5206\u6790\u3057\u307e\u3059\u3002",
            "persona": "\u3053\u306e\u30a2\u30ab\u30a6\u30f3\u30c8\u306f\u9577\u671f\u6295\u8cc7\u5bb6\u5411\u3051\u3067\u3059\u3002",
            "profession": "\u30a2\u30ca\u30ea\u30b9\u30c8",
            "country": "\u65e5\u672c",
            "interested_topics": ["\u5e02\u5834\u5206\u6790", "ETF"],
        }
    ])

    assert result[0]["bio"] == "원문 소개의 한국어 번역"
    assert result[0]["persona"] == "원문 페르소나의 한국어 번역"
    assert result[0]["profession"] == "시장 분석가"
    assert result[0]["country"] == "일본"
    assert result[0]["interested_topics"] == ["시장 분석", "ETF"]


def test_profile_localizer_realigns_out_of_order_translation_response(monkeypatch):
    service = ProfileLocalizationService(api_key="")
    service.client = object()

    def fake_create_chat_completion(*args, **kwargs):
        request_body = json.loads(kwargs["messages"][1]["content"])
        assert request_body["profiles"][0]["_translation_index"] == 0
        assert request_body["profiles"][1]["_translation_index"] == 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "profiles": [
                                    {
                                        "_translation_index": 1,
                                        "bio": "두 번째 소개 번역",
                                        "persona": "두 번째 페르소나 번역",
                                        "profession": "시장 분석가",
                                        "country": "일본",
                                        "interested_topics": ["거시경제"],
                                    },
                                    {
                                        "_translation_index": 0,
                                        "bio": "첫 번째 소개 번역",
                                        "persona": "첫 번째 페르소나 번역",
                                        "profession": "연구원",
                                        "country": "중국",
                                        "interested_topics": ["AI"],
                                    },
                                ]
                            },
                            ensure_ascii=False,
                        ),
                        reasoning_content=None,
                    )
                )
            ]
        )

    monkeypatch.setattr(
        profile_localization_module,
        "create_chat_completion_with_fallback",
        fake_create_chat_completion,
    )

    result = service.localize_profiles([
        {
            "bio": "第一個人物介紹",
            "persona": "第一個人物設定",
            "profession": "研究者",
            "country": "中国",
            "interested_topics": ["AI"],
        },
        {
            "bio": "日本市場の動向を追っています。",
            "persona": "長期投資家向けアカウントです。",
            "profession": "アナリスト",
            "country": "日本",
            "interested_topics": ["マクロ経済"],
        },
    ])

    assert result[0]["bio"] == "첫 번째 소개 번역"
    assert result[0]["persona"] == "첫 번째 페르소나 번역"
    assert result[0]["profession"] == "연구원"
    assert result[0]["country"] == "중국"
    assert result[0]["interested_topics"] == ["AI"]
    assert result[1]["bio"] == "두 번째 소개 번역"
    assert result[1]["persona"] == "두 번째 페르소나 번역"
    assert result[1]["profession"] == "시장 분석가"
    assert result[1]["country"] == "일본"
    assert result[1]["interested_topics"] == ["거시경제"]


def test_profile_localizer_accepts_same_length_response_without_translation_index(monkeypatch):
    service = ProfileLocalizationService(api_key="")
    service.client = object()

    def fake_create_chat_completion(*args, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "profiles": [
                                    {
                                        "bio": "원문 소개 번역",
                                        "persona": "원문 페르소나 번역",
                                        "profession": "시장 분석가",
                                        "country": "일본",
                                        "interested_topics": ["ETF"],
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                        reasoning_content=None,
                    )
                )
            ]
        )

    monkeypatch.setattr(
        profile_localization_module,
        "create_chat_completion_with_fallback",
        fake_create_chat_completion,
    )

    result = service.localize_profiles([
        {
            "bio": "日本市場とETFを分析します。",
            "persona": "長期投資家向けです。",
            "profession": "アナリスト",
            "country": "日本",
            "interested_topics": ["ETF"],
        }
    ])

    assert result[0]["bio"] == "원문 소개 번역"
    assert result[0]["persona"] == "원문 페르소나 번역"
    assert result[0]["profession"] == "시장 분석가"
    assert result[0]["country"] == "일본"
    assert result[0]["interested_topics"] == ["ETF"]


def test_oasis_profile_generator_prompts_require_korean_output():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)

    system_prompt = generator._get_system_prompt(is_individual=True)
    individual_prompt = generator._build_individual_persona_prompt(
        entity_name="JEPI",
        entity_type="company",
        entity_summary="ETF 관련 기업",
        entity_attributes={},
        context="없음",
    )
    group_prompt = generator._build_group_persona_prompt(
        entity_name="JPMorgan Chase & Co.",
        entity_type="organization",
        entity_summary="금융 기관",
        entity_attributes={},
        context="없음",
    )

    assert "한국어" in system_prompt
    assert "한국어 사용" in individual_prompt
    assert "한국어 사용" in group_prompt
