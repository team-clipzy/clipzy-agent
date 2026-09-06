"""
최종 추천 결과 스키마

Re-ranker의 출력을 정의합니다.
"""

from pydantic import BaseModel, Field


# =============================================================================
# LLM 응답 파싱용
# =============================================================================

class RankedVideo(BaseModel):
    """LLM이 선정한 개별 영상"""
    
    video_id: str = Field(description="YouTube 영상 ID")
    rank: int = Field(ge=1, le=6, description="순위 (1-6)")
    reason: str = Field(description="추천 이유 (한국어)")


class RerankerOutput(BaseModel):
    """
    LLM Re-ranker의 원본 출력
    
    개수 검증:
    - 정확히 6개여야 함
    - Pydantic이 자동 검증
    """
    
    recommendations: list[RankedVideo] = Field(
        min_length=6,
        max_length=6,
        description="Top 6 영상 (정확히 6개)",
    )
    overall_strategy: str = Field(
        description="전체 추천 전략 (한국어)",
    )


# =============================================================================
# API 요청/응답 스키마
# =============================================================================

class RecommendRequest(BaseModel):
    """추천 요청"""
    
    user_id: int = Field(
        ...,
        description="사용자 ID",
        examples=[1],
    )
    max_videos_per_query: int = Field(
        default=10,
        ge=1,
        le=50,
        description="검색어당 후보 영상 수",
    )
    force_refresh: bool = Field(
        default=False,
        description="캐시 무시 여부",
    )


class RecommendedVideo(BaseModel):
    """
    최종 추천 영상 (사용자에게 반환)
    
    후보 영상 정보 + LLM 추천 정보
    """
    
    # 순위 정보
    rank: int = Field(description="순위 (1-6)")
    reason: str = Field(description="추천 이유 (한국어)")
    
    # YouTube 영상 정보
    video_id: str
    title: str
    description: str
    channel_id: str
    channel_name: str
    thumbnail_url: str
    published_at: str
    
    # 매칭 정보
    matched_query: str = Field(description="어떤 검색어로 발견됐는지")


class RecommendResponse(BaseModel):
    """추천 응답 - Discovery Agent 최종 결과"""
    
    user_id: int
    
    # 추천 결과
    recommendations: list[RecommendedVideo] = Field(
        description="Top 6 추천 영상",
    )
    overall_strategy: str = Field(
        description="LLM의 전체 추천 전략 설명",
    )
    
    # 과정 정보 (투명성)
    generated_queries: list[str] = Field(
        description="LLM이 생성한 검색어들",
    )
    total_candidates: int = Field(
        description="후보 영상 총 개수",
    )
    
    # 성능 & 비용
    cache_hits: int
    cache_misses: int
    processing_time_ms: int
    tokens_used_query: int = Field(description="Query 생성 토큰")
    tokens_used_rerank: int = Field(description="Re-rank 토큰")
    total_cost_usd: float = Field(description="총 예상 비용 (USD)")