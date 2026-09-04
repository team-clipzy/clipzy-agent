"""
Content Discovery Agent - Pydantic 스키마

역할:
- Discovery API의 요청/응답 타입 정의
- LLM 검색어 생성 → YouTube 검색 → 결과 통합 흐름
"""

from pydantic import BaseModel, Field


# =============================================================================
# 요청 스키마
# =============================================================================

class DiscoverySearchRequest(BaseModel):
    """
    콘텐츠 발견 요청
    
    두 가지 사용 방식:
    1. user_id만 전달 → 저장된 프로필로 자동 실행
    2. 옵션 커스터마이징 → max_videos_per_query 등 조정
    """

    user_id: int = Field(
        ...,
        description="사용자 ID (Qdrant에서 프로필 조회)",
        examples=[1],
    )
    max_videos_per_query: int = Field(
        default=10,
        ge=1,
        le=50,
        description="검색어당 반환할 영상 수 (기본 10개, 최대 50개)",
    )
    force_refresh: bool = Field(
        default=False,
        description="True면 캐시 무시하고 새로 검색 (개발/테스트용)",
    )


# =============================================================================
# 응답 스키마
# =============================================================================

class VideoCandidate(BaseModel):
    """
    후보 영상 정보
    
    YouTube Search API 결과에서 필요한 정보만 추출
    """

    video_id: str = Field(description="YouTube 영상 ID")
    title: str = Field(description="영상 제목")
    description: str = Field(description="영상 설명 (일부)")
    channel_id: str = Field(description="채널 ID")
    channel_name: str = Field(description="채널 이름")
    thumbnail_url: str = Field(description="썸네일 URL")
    published_at: str = Field(description="게시일")
    matched_query: str = Field(
        description="이 영상이 매칭된 검색어",
    )


class DiscoverySearchResponse(BaseModel):
    """
    콘텐츠 발견 응답
    
    검색어 생성부터 후보 영상 확보까지 전체 결과
    """

    user_id: int
    
    # 생성된 검색어 정보
    generated_queries: list[str] = Field(
        description="LLM이 생성한 검색어 5개",
    )
    query_reasoning: str = Field(
        description="검색어 생성 전략 (한국어)",
    )
    
    # 검색 결과
    total_candidates: int = Field(
        description="중복 제거 후 총 후보 영상 수",
    )
    videos: list[VideoCandidate] = Field(
        description="후보 영상 리스트 (중복 제거됨)",
    )
    
    # 성능 & 캐싱 정보
    cache_hits: int = Field(
        description="캐시에서 가져온 검색 개수 (5개 중)",
    )
    cache_misses: int = Field(
        description="새로 API 호출한 검색 개수 (5개 중)",
    )
    processing_time_ms: int = Field(
        description="전체 처리 시간 (밀리초)",
    )
    tokens_used: int = Field(
        description="LLM에 사용된 토큰 수",
    )