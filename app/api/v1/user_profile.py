"""
사용자 학습 프로필 API
프로필 생성, 조회, 삭제 엔드포인트
"""

from fastapi import APIRouter, HTTPException

from app.core.logger import logger
from app.schemas.user_profile import (
    BuildProfileRequest,
    GetProfileResponse,
    ProfileResponse,
)
from app.services.user_profile_service import get_user_profile_service

router = APIRouter(prefix="/user-profile", tags=["User Profile"])


@router.post(
    "/build",
    response_model=ProfileResponse,
    summary="사용자 학습 프로필 생성/업데이트",
)
async def build_profile(request: BuildProfileRequest) -> ProfileResponse:
    """
    사용자 학습 데이터를 종합해 임베딩 벡터를 생성하고 Qdrant에 저장합니다.

    **입력 데이터:**
    - 학습 목표 (TRAVEL/DAILY/BUSINESS)
    - 영어 수준 (BEGINNER/INTERMEDIATE/ADVANCED)
    - 최근 수집 단어 (최대 20개)
    - 채팅 약점 표현 (최대 10개)
    - 정답률 낮은 단어 (최대 10개)
    - 완주한 영상 이력

    **처리 과정:**
    1. 데이터를 자연어 프로필 텍스트로 변환
    2. OpenAI 임베딩 API로 1536차원 벡터 생성
    3. Qdrant `user_profiles` 컬렉션에 저장

    **결과:**
    - 이후 이 벡터로 개인화 추천에 활용
    """
    try:
        service = get_user_profile_service()
        result = await service.build_and_save_profile(request)
        return ProfileResponse(**result)

    except Exception as e:
        logger.error(f"프로필 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{user_id}",
    response_model=GetProfileResponse,
    summary="저장된 사용자 프로필 조회",
)
async def get_profile(user_id: int) -> GetProfileResponse:
    """
    Qdrant에 저장된 사용자 프로필을 조회합니다.

    - 프로필 없으면 exists=false 반환
    - 있으면 프로필 텍스트 + 메타데이터 반환
    """
    try:
        service = get_user_profile_service()
        profile = service.get_profile(user_id)

        if profile is None:
            return GetProfileResponse(user_id=user_id, exists=False)

        return GetProfileResponse(
            user_id=user_id,
            exists=True,
            profile=ProfileResponse(**profile),
        )

    except Exception as e:
        logger.error(f"프로필 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{user_id}",
    summary="사용자 프로필 삭제 (GDPR)",
)
async def delete_profile(user_id: int) -> dict:
    """
    사용자 프로필을 완전히 삭제합니다.

    - GDPR 데이터 삭제 요청 대응용
    - 개인정보처리방침 상의 삭제 절차
    """
    try:
        service = get_user_profile_service()
        success = service.delete_profile(user_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"프로필을 찾을 수 없습니다: user_id={user_id}",
            )

        return {
            "status": "success",
            "user_id": user_id,
            "message": "프로필이 삭제되었습니다",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프로필 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))