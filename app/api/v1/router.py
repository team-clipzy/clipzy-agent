"""
API v1 라우터 통합
모든 v1 엔드포인트를 여기서 통합합니다.
"""

from fastapi import APIRouter

from app.api.v1 import health, query, user_profile

# v1 통합 라우터
api_router = APIRouter(prefix="/api/v1")

# 각 도메인 라우터 등록
api_router.include_router(health.router)
api_router.include_router(user_profile.router)
api_router.include_router(query.router)

# TODO: 추천 시스템 라우터 추가 예정
# api_router.include_router(recommendation.router)