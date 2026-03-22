"""
Profile 형식 생성이 OASIS 요구사항을 충족하는지 검사한다.
검증 항목:
1. Twitter Profile이 CSV 형식으로 생성되는지
2. Reddit Profile이 상세한 JSON 형식으로 생성되는지
"""

import os
import sys
import json
import csv
import tempfile

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile


def test_profile_formats():
    """Profile 형식을 테스트한다."""
    print("=" * 60)
    print("OASIS Profile 형식 테스트")
    print("=" * 60)
    
    # 테스트용 Profile 데이터 생성
    test_profiles = [
        OasisAgentProfile(
            user_id=0,
            user_name="test_user_123",
            name="테스트 사용자",
            bio="검증을 위한 테스트 사용자입니다",
            persona="테스트 사용자는 소셜 토론에 적극적으로 참여합니다.",
            karma=1500,
            friend_count=100,
            follower_count=200,
            statuses_count=500,
            age=25,
            gender="male",
            mbti="INTJ",
            country="South Korea",
            profession="Student",
            interested_topics=["Technology", "Education"],
            source_entity_uuid="test-uuid-123",
            source_entity_type="Student",
        ),
        OasisAgentProfile(
            user_id=1,
            user_name="org_official_456",
            name="공식 기관",
            bio="기관의 공식 계정입니다",
            persona="공식 입장을 전달하는 기관 계정입니다.",
            karma=5000,
            friend_count=50,
            follower_count=10000,
            statuses_count=200,
            profession="Organization",
            interested_topics=["Public Policy", "Announcements"],
            source_entity_uuid="test-uuid-456",
            source_entity_type="University",
        ),
    ]
    
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    
    # 임시 디렉터리 사용
    with tempfile.TemporaryDirectory() as temp_dir:
        twitter_path = os.path.join(temp_dir, "twitter_profiles.csv")
        reddit_path = os.path.join(temp_dir, "reddit_profiles.json")
        
        # Twitter CSV 형식 테스트
        print("\n1. Twitter Profile 테스트 (CSV 형식)")
        print("-" * 40)
        generator._save_twitter_csv(test_profiles, twitter_path)
        
        # CSV 읽기 및 검증
        with open(twitter_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"   파일: {twitter_path}")
        print(f"   행 수: {len(rows)}")
        print(f"   헤더: {list(rows[0].keys())}")
        print(f"\n   예시 데이터 (1행):")
        for key, value in rows[0].items():
            print(f"     {key}: {value}")
        
        # 필수 필드 검증
        required_twitter_fields = ['user_id', 'user_name', 'name', 'bio', 
                                   'friend_count', 'follower_count', 'statuses_count', 'created_at']
        missing = set(required_twitter_fields) - set(rows[0].keys())
        if missing:
            print(f"\n   [오류] 누락된 필드: {missing}")
        else:
            print(f"\n   [통과] 모든 필수 필드가 존재합니다")
        
        # Reddit JSON 형식 테스트
        print("\n2. Reddit Profile 테스트 (상세 JSON 형식)")
        print("-" * 40)
        generator._save_reddit_json(test_profiles, reddit_path)
        
        # JSON 읽기 및 검증
        with open(reddit_path, 'r', encoding='utf-8') as f:
            reddit_data = json.load(f)
        
        print(f"   파일: {reddit_path}")
        print(f"   항목 수: {len(reddit_data)}")
        print(f"   필드: {list(reddit_data[0].keys())}")
        print(f"\n   예시 데이터 (1번째):")
        print(json.dumps(reddit_data[0], ensure_ascii=False, indent=4))
        
        # 상세 형식 필드 검증
        required_reddit_fields = ['realname', 'username', 'bio', 'persona']
        optional_reddit_fields = ['age', 'gender', 'mbti', 'country', 'profession', 'interested_topics']
        
        missing = set(required_reddit_fields) - set(reddit_data[0].keys())
        if missing:
            print(f"\n   [오류] 필수 필드 누락: {missing}")
        else:
            print(f"\n   [통과] 모든 필수 필드가 존재합니다")
        
        present_optional = set(optional_reddit_fields) & set(reddit_data[0].keys())
        print(f"   [정보] 선택 필드: {present_optional}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


def show_expected_formats():
    """OASIS가 기대하는 형식을 보여준다."""
    print("\n" + "=" * 60)
    print("OASIS가 기대하는 Profile 형식 참고")
    print("=" * 60)
    
    print("\n1. Twitter Profile (CSV 형식)")
    print("-" * 40)
    twitter_example = """user_id,user_name,name,bio,friend_count,follower_count,statuses_count,created_at
0,user0,사용자 제로,기술에 관심이 있는 사용자 제로입니다.,100,150,500,2023-01-01
1,user1,사용자 원,기술 애호가이자 커피를 좋아합니다.,200,250,1000,2023-01-02"""
    print(twitter_example)
    
    print("\n2. Reddit Profile (상세 JSON 형식)")
    print("-" * 40)
    reddit_example = [
        {
            "realname": "김민수",
            "username": "millerhospitality",
            "bio": "환대와 관광 분야에 열정을 가지고 있습니다.",
            "persona": "민수는 환대 및 관광 업계에서 오랜 경력을 쌓은 전문가입니다...",
            "age": 40,
            "gender": "male",
            "mbti": "ESTJ",
            "country": "UK",
            "profession": "환대 및 관광",
            "interested_topics": ["경제", "비즈니스"]
        }
    ]
    print(json.dumps(reddit_example, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    test_profile_formats()
    show_expected_formats()
