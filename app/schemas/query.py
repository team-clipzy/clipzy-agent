"""
Query Generator 관련 Pydantic 스키마

역할:
- LLM 응답을 타입 안전하게 파싱
- API 요청/응답 검증
- Swagger 문서 자동 생성
"""

from pydantic import BaseModel, Field


# =============================================================================
# LLM 응답 파싱용 스키마
# =============================================================================

class GeneratedQueries(BaseModel):
    """
    LLM이 생성한 검색어 결과
    
    Structured Output 파싱용:
    - OpenAI response_format={"type": "json_object"}로 JSON 강제
    - Pydantic이 자동으로 타입 검증
    """
    
    queries: list[str] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="생성된 YouTube 검색어 5개",
    )
    reasoning: str = Field(
        ...,
        description="검색어 생성 전략 설명 (한국어)",
    )


# =============================================================================
# API 요청/응답 스키마
# =============================================================================

class GenerateQueryRequest(BaseModel):
    """
    검색어 생성 요청
    
    옵션 1: user_id로 저장된 프로필 활용 (기본)
    옵션 2: profile_text 직접 전달 (테스트/실험용)
    """
    
    user_id: int | None = Field(
        default=None,
        description="사용자 ID (Qdrant에서 프로필 조회)",
    )
    profile_text: str | None = Field(
        default=None,
        description="프로필 텍스트 직접 전달 (테스트용, user_id 없을 때 사용)",
    )
    learning_goal: str | None = Field(
        default=None,
        description="학습 목표 (프로필 없을 때 필수)",
    )
    absolute_level: str | None = Field(
        default=None,
        description="영어 수준 (프로필 없을 때 필수)",
    )


class GenerateQueryResponse(BaseModel):
    """검색어 생성 응답"""
    
    user_id: int | None
    queries: list[str] = Field(description="생성된 검색어 5개")
    reasoning: str = Field(description="생성 전략 설명")
    tokens_used: int = Field(description="사용된 토큰 수 (비용 추적)")
    model: str = Field(description="사용된 LLM 모델")