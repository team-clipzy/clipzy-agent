"""
임베딩 & 벡터 검색 테스트 API
개발/디버깅용 엔드포인트입니다.
"""

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.logger import logger
from app.schemas.embedding import (
    EmbedRequest,
    EmbedResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    UpsertRequest,
)
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import get_qdrant_service

router = APIRouter(prefix="/embedding", tags=["Embedding"])


@router.post(
    "/embed",
    response_model=EmbedResponse,
    summary="텍스트를 벡터로 변환",
)
async def embed_text(request: EmbedRequest) -> EmbedResponse:
    """
    텍스트를 임베딩 벡터로 변환합니다.

    - 응답은 미리보기 (앞 5개 값)만 포함
    - 실제 벡터는 1536차원
    """
    try:
        embedding_service = get_embedding_service()
        vector = await embedding_service.embed(request.text)

        return EmbedResponse(
            text=request.text,
            embedding_preview=vector[:5],  # 앞 5개만 미리보기
            dimension=len(vector),
            model=settings.openai_model_embedding,
        )
    except Exception as e:
        logger.error(f"임베딩 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upsert",
    summary="텍스트를 임베딩 후 Qdrant에 저장",
)
async def upsert_text(request: UpsertRequest) -> dict:
    """
    텍스트를 임베딩 후 Qdrant에 저장합니다.

    Qdrant 대시보드(localhost:6333/dashboard)에서 확인 가능
    """
    try:
        # 1. 임베딩 생성
        embedding_service = get_embedding_service()
        vector = await embedding_service.embed(request.text)

        # 2. Qdrant에 저장 (payload에 원본 텍스트 포함)
        qdrant = get_qdrant_service()
        payload = {"text": request.text}
        if request.metadata:
            payload.update(request.metadata)

        point_id = qdrant.upsert_point(
            collection_name=settings.qdrant_collection_video,  # 테스트용으로 videos 컬렉션 사용
            embedding=vector,
            payload=payload,
        )

        return {
            "status": "success",
            "point_id": point_id,
            "collection": settings.qdrant_collection_video,
            "text": request.text,
        }
    except Exception as e:
        logger.error(f"upsert 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="유사도 검색",
)
async def search_similar(request: SearchRequest) -> SearchResponse:
    """
    쿼리 텍스트와 가장 유사한 항목을 검색합니다.

    - 코사인 유사도 기반
    - score: 0~1 (높을수록 유사)
    """
    try:
        # 1. 쿼리 임베딩
        embedding_service = get_embedding_service()
        query_vector = await embedding_service.embed(request.query)

        # 2. Qdrant 검색
        qdrant = get_qdrant_service()
        raw_results = qdrant.search(
            collection_name=settings.qdrant_collection_video,
            query_vector=query_vector,
            top_k=request.top_k,
        )

        # 3. 응답 포맷팅
        results = [
            SearchResult(
                id=r["id"],
                score=r["score"],
                text=r["payload"].get("text", ""),
                metadata={k: v for k, v in r["payload"].items() if k != "text"},
            )
            for r in raw_results
        ]

        return SearchResponse(
            query=request.query,
            results=results,
            total=len(results),
        )
    except Exception as e:
        logger.error(f"검색 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/clear",
    summary="테스트 컬렉션 초기화 (⚠️ 개발용)",
)
async def clear_test_collection() -> dict:
    """
    테스트용 컬렉션의 모든 데이터를 삭제합니다.

    ⚠️ 개발 환경에서만 사용!
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="개발 환경에서만 사용 가능합니다",
        )

    qdrant = get_qdrant_service()
    qdrant.clear_collection(settings.qdrant_collection_video)

    return {
        "status": "success",
        "message": f"컬렉션 '{settings.qdrant_collection_video}' 초기화 완료",
    }