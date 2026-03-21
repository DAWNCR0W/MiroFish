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
                "bio": "중국어 소개의 한국어 번역",
                "persona": "중국어 페르소나의 한국어 번역",
                "profession": "금융 분석가",
                "country": "중국",
                "interested_topics": ["시장 분석", "ETF"],
            }
        ]

    monkeypatch.setattr(service, "_translate_batch", fake_translate)

    result = service.localize_profiles([
        {
            "bio": "\u4e13\u6ce8\u4e8eETF\u6295\u8d44\u5206\u6790\uff0c\u63d0\u4f9b\u6700\u65b0\u5e02\u573a\u52a8\u6001\u4e0e\u7b56\u7565\u5efa\u8bae\u3002",
            "persona": "\u8be5\u8d26\u6237\u4e3b\u8981\u9762\u5411\u957f\u671f\u6295\u8d44\u8005\u3002",
            "profession": "\u91d1\u878d\u5206\u6790\u5e08",
            "country": "\u4e2d\u56fd",
            "interested_topics": ["\u5e02\u573a\u5206\u6790", "ETF"],
        }
    ])

    assert result[0]["bio"] == "중국어 소개의 한국어 번역"
    assert result[0]["persona"] == "중국어 페르소나의 한국어 번역"
    assert result[0]["profession"] == "금융 분석가"
    assert result[0]["country"] == "중국"
    assert result[0]["interested_topics"] == ["시장 분석", "ETF"]


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
    assert "중국어를 사용하세요" not in system_prompt
    assert "한국어 사용" in individual_prompt
    assert "중국어를 사용하세요" not in individual_prompt
    assert "한국어 사용" in group_prompt
    assert "중국어를 사용하세요" not in group_prompt
