"""
임베딩 관련 Pydantic 스키마
API 요청/응답 데이터 검증 및 직렬화
"""

from typing import Any

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    """단일 텍스트 임베딩 요청"""

    text: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="임베딩할 텍스트",
        examples=["I love learning English through YouTube"],
    )


class EmbedBatchRequest(BaseModel):
    """여러 텍스트 배치 임베딩 요청"""

    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="임베딩할 텍스트 리스트 (최대 100개)",
    )


class EmbedResponse(BaseModel):
    """임베딩 응답"""

    text: str
    embedding_preview: list[float] = Field(
        description="임베딩 벡터 미리보기 (앞 5개 값만)"
    )
    dimension: int = Field(description="벡터 차원 수")
    model: str = Field(description="사용된 모델")


class UpsertRequest(BaseModel):
    """Qdrant에 텍스트 저장 요청"""

    text: str = Field(..., min_length=1, description="저장할 텍스트")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="추가 메타데이터 (예: video_id, title 등)",
        examples=[{"category": "travel", "level": "beginner"}],
    )


class SearchRequest(BaseModel):
    """유사도 검색 요청"""

    query: str = Field(
        ...,
        min_length=1,
        description="검색 쿼리",
        examples=["study English videos"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="반환할 결과 개수",
    )


class SearchResult(BaseModel):
    """검색 결과 단일 항목"""

    id: str | int
    score: float = Field(description="유사도 점수 (0~1, 높을수록 유사)")
    text: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    """검색 응답"""

    query: str
    results: list[SearchResult]
    total: int