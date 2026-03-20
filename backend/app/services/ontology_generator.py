"""
본체 생성 서비스
인터페이스 1: 텍스트 내용을 분석해 사회 시뮬레이션에 적합한 엔티티와 관계 유형 정의를 생성합니다.
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.ontology import normalize_ontology


# 본체 생성용 시스템 프롬프트
ONTOLOGY_SYSTEM_PROMPT = """당신은 전문 지식 그래프 본체 설계 전문가입니다. 주어진 텍스트 내용과 시뮬레이션 요구사항을 분석해 **소셜 미디어 여론 시뮬레이션**에 적합한 엔티티 유형과 관계 유형을 설계하세요.

**중요: 반드시 유효한 JSON 형식 데이터만 출력하고, 다른 내용은 출력하지 마세요.**

## 핵심 작업 배경

우리는 **소셜 미디어 여론 시뮬레이션 시스템**을 구축하고 있습니다. 이 시스템에서:
- 각 엔티티는 소셜 미디어에서 발언하고, 상호작용하고, 정보를 확산할 수 있는 "계정" 또는 "주체"입니다.
- 엔티티는 서로 영향을 주고, 전파하고, 댓글을 달고, 응답합니다.
- 우리는 여론 사건에서 각 주체의 반응과 정보 확산 경로를 시뮬레이션해야 합니다.

따라서 **엔티티는 현실에 실제로 존재하며 소셜 미디어에서 발언과 상호작용이 가능한 주체**여야 합니다:

**가능한 것**:
- 구체적인 개인(공인, 당사자, 의견 리더, 전문가/학자, 일반인)
- 회사, 기업(공식 계정 포함)
- 조직 기관(대학, 협회, NGO, 노조 등)
- 정부 부처, 규제 기관
- 미디어 기관(신문, 방송사, 자매체, 웹사이트)
- 소셜 미디어 플랫폼 자체
- 특정 집단 대표(동문회, 팬클럽, 권리 보호 집단 등)

**불가능한 것**:
- 추상 개념(예: "여론", "감정", "추세")
- 주제/화제(예: "학술 윤리", "교육 개혁")
- 관점/태도(예: "찬성 측", "반대 측")

## 출력 형식

다음 구조를 가진 JSON 형식으로 출력하세요:

```json
{
    "entity_types": [
        {
            "name": "엔티티 유형 이름（영문, PascalCase）",
            "description": "짧은 설명（영문, 100자 이하）",
            "attributes": [
                {
                    "name": "속성명（영문, snake_case）",
                    "type": "text",
                    "description": "속성 설명"
                }
            ],
            "examples": ["예시 엔티티1", "예시 엔티티2"]
        }
    ],
    "edge_types": [
        {
            "name": "관계 유형 이름（영문, UPPER_SNAKE_CASE）",
            "description": "짧은 설명（영문, 100자 이하）",
            "source_targets": [
                {"source": "원본 엔티티 유형", "target": "대상 엔티티 유형"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "텍스트 내용에 대한 간단한 분석 설명(한국어)"
}
```

## JSON 형식 강제 규칙

- `entity_types`는 반드시 배열이어야 합니다.
- `edge_types`는 반드시 배열이어야 하며, 절대 빈 배열이면 안 됩니다.
- `attributes`는 반드시 배열이어야 합니다. 문자열, 숫자, 객체 단일값으로 출력하면 안 됩니다.
- `examples`는 반드시 문자열 배열이어야 합니다. 문자열 단일값으로 출력하면 안 됩니다.
- `source_targets`는 반드시 `{ "source": "...", "target": "..." }` 객체의 배열이어야 합니다. 문자열로 출력하면 안 됩니다.
- `analysis_summary`는 반드시 비어 있지 않은 한국어 문자열이어야 합니다.
- JSON 바깥의 설명, 주석, 코드 블록, 마크다운을 절대 추가하지 마세요.

## 출력 전 내부 점검

출력하기 전에 반드시 스스로 다음을 만족하는지 확인하세요:
- `len(entity_types) == 10`
- `len(edge_types) >= 6`
- 모든 `attributes` 필드가 배열
- 모든 `examples` 필드가 배열
- 모든 `source_targets` 필드가 배열
- `analysis_summary`가 비어 있지 않음

하나라도 만족하지 못하면, 출력 전에 JSON을 스스로 수정하세요.

## 설계 가이드(매우 중요!)

### 1. 엔티티 유형 설계 - 반드시 엄격히 준수

**수량 요구사항: 반드시 정확히 10개 엔티티 유형**

**계층 구조 요구사항(구체 유형과 기본 유형을 모두 포함해야 함)**:

10개 엔티티 유형은 다음 계층을 반드시 포함해야 합니다:

A. **기본 유형(반드시 포함, 목록의 마지막 2개에 배치)**:
   - `Person`: 모든 자연인 개체의 기본 유형. 한 사람이 다른 더 구체적인 인물 유형에 속하지 않으면 이 유형으로 분류합니다.
   - `Organization`: 모든 조직 기관의 기본 유형. 한 조직이 다른 더 구체적인 조직 유형에 속하지 않으면 이 유형으로 분류합니다.

B. **구체 유형(8개, 텍스트 내용에 따라 설계)**:
   - 텍스트에 등장하는 주요 역할을 기준으로 더 구체적인 유형을 설계합니다.
   - 예: 텍스트가 학술 사건을 다루면 `Student`, `Professor`, `University`가 있을 수 있습니다.
   - 예: 텍스트가 상업 사건을 다루면 `Company`, `CEO`, `Employee`가 있을 수 있습니다.

**기본 유형이 필요한 이유**:
- 텍스트에는 "초중고 교사", "행인", "어느 네티즌" 같은 다양한 인물이 등장할 수 있습니다.
- 전용 유형이 없으면 `Person`으로 분류해야 합니다.
- 마찬가지로 소규모 조직, 임시 단체 등은 `Organization`으로 분류해야 합니다.

**구체 유형 설계 원칙**:
- 텍스트에서 자주 등장하거나 핵심적인 역할 유형을 식별하세요.
- 각 구체 유형은 경계가 명확해야 하며 중복을 피해야 합니다.
- description은 이 유형과 기본 유형의 차이를 명확히 설명해야 합니다.

### 2. 관계 유형 설계

- 수량: 6-10개
- 관계는 소셜 미디어 상호작용의 실제 연결을 반영해야 합니다.
- 관계의 source_targets가 정의한 엔티티 유형을 포괄하도록 하세요.
- 관계 유형을 도메인에 맞게 충분히 설계하되, 애매하더라도 `edge_types`를 비워 두면 안 됩니다.
- 텍스트 특화 관계가 불명확하면 최소한 다음 일반 관계 중 4개 이상을 포함하세요:
  `AFFILIATED_WITH`, `REPORTS_ON`, `RESPONDS_TO`, `SUPPORTS`, `OPPOSES`, `COLLABORATES_WITH`

### 3. 속성 설계

- 각 엔티티 유형당 1-3개의 핵심 속성
- **주의**: 속성명에는 `name`, `uuid`, `group_id`, `created_at`, `summary`를 사용할 수 없습니다(시스템 예약어)
- 권장: `full_name`, `title`, `role`, `position`, `location`, `description` 등

## 엔티티 유형 참고

**개인 유형(구체)**:
- Student: 학생
- Professor: 교수/학자
- Journalist: 기자
- Celebrity: 연예인/인플루언서
- Executive: 고위 임원
- Official: 정부 관료
- Lawyer: 변호사
- Doctor: 의사

**개인 유형(기본)**:
- Person: 모든 자연인(위의 구체 유형에 속하지 않을 때 사용)

**조직 유형(구체)**:
- University: 대학
- Company: 회사/기업
- GovernmentAgency: 정부 기관
- MediaOutlet: 미디어 기관
- Hospital: 병원
- School: 초중고
- NGO: 비정부 조직

**조직 유형(기본)**:
- Organization: 모든 조직 기관(위의 구체 유형에 속하지 않을 때 사용)

## 관계 유형 참고

- WORKS_FOR: 재직 중
- STUDIES_AT: 재학 중
- AFFILIATED_WITH: 소속됨
- REPRESENTS: 대표함
- REGULATES: 규제함
- REPORTS_ON: 보도함
- COMMENTS_ON: 논평함
- RESPONDS_TO: 대응함
- SUPPORTS: 지지함
- OPPOSES: 반대함
- COLLABORATES_WITH: 협력함
- COMPETES_WITH: 경쟁함
"""


FALLBACK_EDGE_TYPES = [
    {
        "name": "AFFILIATED_WITH",
        "description": "Is affiliated with an organization or group.",
        "source_targets": [
            {"source": "Person", "target": "Organization"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "REPORTS_ON",
        "description": "Reports on a person, organization, or issue.",
        "source_targets": [
            {"source": "Person", "target": "Person"},
            {"source": "Person", "target": "Organization"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "RESPONDS_TO",
        "description": "Responds to a statement, action, or actor.",
        "source_targets": [
            {"source": "Person", "target": "Person"},
            {"source": "Organization", "target": "Person"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "SUPPORTS",
        "description": "Shows support for another actor or group.",
        "source_targets": [
            {"source": "Person", "target": "Person"},
            {"source": "Person", "target": "Organization"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "OPPOSES",
        "description": "Shows opposition to another actor or group.",
        "source_targets": [
            {"source": "Person", "target": "Person"},
            {"source": "Person", "target": "Organization"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
    {
        "name": "COLLABORATES_WITH",
        "description": "Collaborates with another actor or group.",
        "source_targets": [
            {"source": "Person", "target": "Person"},
            {"source": "Person", "target": "Organization"},
            {"source": "Organization", "target": "Organization"},
        ],
        "attributes": [],
    },
]


class OntologyGenerator:
    """
    본체 생성기
    텍스트 내용을 분석해 엔티티와 관계 유형 정의를 생성합니다.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        본체 정의를 생성합니다.
        
        인자:
            document_texts: 문서 텍스트 목록
            simulation_requirement: 시뮬레이션 요구사항 설명
            additional_context: 추가 컨텍스트
            
        반환값:
            본체 정의(entity_types, edge_types 등)
        """
        # 사용자 메시지를 구성합니다.
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # LLM을 호출합니다.
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # 검증 및 후처리를 수행합니다.
        result = self._validate_and_process(result)
        
        return result
    
    # LLM에 전달할 텍스트 최대 길이(5만 자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """사용자 메시지 구성"""
        
        # 텍스트를 합칩니다.
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # 텍스트가 5만 자를 넘으면 자릅니다(LLM에 전달되는 내용만 영향을 받으며 그래프 구축에는 영향을 주지 않습니다).
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(원문 총 {original_length}자, 본체 분석을 위해 앞의 {self.MAX_TEXT_LENGTH_FOR_LLM}자만 사용)..."
        
        message = f"""## 시뮬레이션 요구사항

{simulation_requirement}

## 문서 내용

{combined_text}
"""
        
        if additional_context:
            message += f"""
## 추가 설명

{additional_context}
"""
        
        message += """
위 내용을 바탕으로 사회 여론 시뮬레이션에 적합한 엔티티 유형과 관계 유형을 설계하세요.

**반드시 지켜야 하는 규칙**:
1. 반드시 정확히 10개의 엔티티 유형을 출력해야 합니다
2. 마지막 2개는 기본 유형이어야 합니다: Person(개인 기본)과 Organization(조직 기본)
3. 앞의 8개는 텍스트 내용에 따라 설계한 구체 유형이어야 합니다
4. 모든 엔티티 유형은 현실에서 발언 가능한 주체여야 하며, 추상 개념이어서는 안 됩니다
5. 속성명에는 name, uuid, group_id 등 예약어를 사용할 수 없으며 full_name, org_name 등으로 대체해야 합니다
6. attributes는 반드시 배열이어야 하며 문자열이나 숫자로 출력하면 안 됩니다
7. source_targets는 반드시 배열이어야 하며 문자열로 출력하면 안 됩니다
8. edge_types는 절대 빈 배열이면 안 됩니다. 애매하면 일반 관계 유형을 사용하세요
9. analysis_summary는 반드시 비어 있지 않은 한국어 문자열이어야 합니다
10. 출력 직전에 위 규칙을 다시 점검하고, 규칙을 만족하도록 JSON을 스스로 수정한 뒤 답변하세요
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 검증 및 후처리"""
        result = normalize_ontology(result)
        
        # 로컬 그래프 추출기 제한: 최대 10개의 사용자 정의 엔티티 유형, 최대 10개의 사용자 정의 엣지 유형
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # 기본 유형을 정의합니다.
        person_fallback = {
            "name": "Person",
            "description": "다른 구체적인 개인 유형에 맞지 않는 모든 개인.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "사람의 전체 이름"},
                {"name": "role", "type": "text", "description": "역할 또는 직업"}
            ],
            "examples": ["일반 시민", "익명 네티즌"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "다른 구체적인 조직 유형에 맞지 않는 모든 조직.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "조직 이름"},
                {"name": "org_type", "type": "text", "description": "조직 유형"}
            ],
            "examples": ["소규모 사업체", "커뮤니티 그룹"]
        }
        
        # 이미 기본 유형이 있는지 확인합니다.
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # 추가해야 할 기본 유형
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # 추가 후 10개를 넘으면 일부 기존 유형을 제거해야 합니다.
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 얼마나 제거해야 하는지 계산합니다.
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 뒤에서부터 제거해 앞쪽의 더 중요한 구체 유형을 보존합니다.
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # 기본 유형을 추가합니다.
            result["entity_types"].extend(fallbacks_to_add)

        if not result["edge_types"]:
            result["edge_types"] = [dict(edge) for edge in FALLBACK_EDGE_TYPES]
        
        # 최종적으로 제한을 넘지 않도록 보장합니다(방어적 프로그래밍).
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return normalize_ontology(result)
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        본체 정의를 Python 코드로 변환합니다(ontology.py와 유사).
        
        인자:
            ontology: 본체 정의
            
        반환값:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            '사용자 정의 엔티티 유형 정의',
            'MiroFish가 자동 생성한 사회 여론 시뮬레이션용 코드',
            '"""',
            '',
            'from pydantic import Field',
            'from pydantic import BaseModel',
            '',
            '',
            '# ============== 엔티티 유형 정의 ==============',
            '',
        ]
        
        # 엔티티 유형을 생성합니다.
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"{name} 엔티티입니다.")
            
            code_lines.append(f'class {name}(BaseModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: str = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== 관계 유형 정의 ==============')
        code_lines.append('')
        
        # 관계 유형을 생성합니다.
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스 이름으로 변환합니다.
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"{name} 관계입니다.")
            
            code_lines.append(f'class {class_name}(BaseModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: str = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 유형 딕셔너리를 생성합니다.
        code_lines.append('# ============== 유형 구성 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 엣지의 source_targets 매핑을 생성합니다.
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
