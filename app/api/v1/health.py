"""
헬스체크 API
서버 상태 및 의존성 확인용 엔드포인트
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.services.qdrant_service import get_qdrant_service

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="기본 헬스체크")
async def health_check() -> dict[str, Any]:
    """
    서버가 정상 동작 중인지 확인합니다.
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/ready", summary="준비 상태 확인")
async def readiness_check() -> dict[str, Any]:
    """
    서버가 요청을 처리할 준비가 되었는지 확인합니다.
    """
    # Qdrant 연결 확인
    qdrant = get_qdrant_service()
    qdrant_ok = qdrant.health_check()

    checks = {
        "database": "not_configured_yet",
        "redis": "not_configured_yet",
        "qdrant": "healthy" if qdrant_ok else "unhealthy",
        "openai": "configured" if settings.openai_api_key else "not_configured",
    }

    all_ready = all(
        v in ("healthy", "configured", "not_configured_yet") for v in checks.values()
    )

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/qdrant", summary="Qdrant 상세 정보")
async def qdrant_info() -> dict[str, Any]:
    """
    Qdrant 컬렉션 정보를 조회합니다.
    """
    qdrant = get_qdrant_service()

    # 컬렉션 없으면 생성
    qdrant.ensure_collections()

    return {
        "videos": qdrant.get_collection_info(settings.qdrant_collection_video),
        "users": qdrant.get_collection_info(settings.qdrant_collection_user),
    }