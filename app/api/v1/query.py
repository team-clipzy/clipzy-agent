"""
Query Generator 테스트 API

역할:
- LLM 기반 검색어 생성을 실제 테스트할 수 있는 엔드포인트
- 개발/디버깅 용도 (프로덕션에서는 Agent 워크플로우 일부로 통합)

두 가지 사용 방법:
1. user_id로 저장된 프로필 활용 (실제 사용 시나리오)
2. profile_text 직접 전달 (실험/디버깅)
"""

from fastapi import APIRouter, HTTPException

from app.agents.discovery.query_generator import get_query_generator
from app.core.config import settings
from app.core.logger import logger
from app.schemas.query import GenerateQueryRequest, GenerateQueryResponse
from app.services.user_profile_service import get_user_profile_service

router = APIRouter(prefix="/query", tags=["Query Generator"])


@router.post(
    "/generate",
    response_model=GenerateQueryResponse,
    summary="사용자 프로필 기반 YouTube 검색어 5개 생성",
)
async def generate_queries(request: GenerateQueryRequest) -> GenerateQueryResponse:
    """
    LLM(gpt-4o-mini)을 사용해 사용자 맞춤 YouTube 검색어를 생성합니다.

    **두 가지 입력 방식:**

    1. `user_id`만 전달:
       - Qdrant에서 저장된 프로필 조회
       - 실제 서비스 시나리오

    2. `profile_text` + `learning_goal` + `absolute_level` 전달:
       - 프로필 직접 지정
       - 테스트/실험용

    **동작 과정:**
    1. 프로필 로드 (DB 또는 요청)
    2. 프롬프트 조립
    3. OpenAI API 호출 (JSON 응답 강제)
    4. Pydantic으로 응답 검증
    5. 검색어 5개 반환

    **비용:**
    - 호출당 약 $0.0002 (0.03원)
    - gpt-4o-mini 사용
    """
    try:
        # ─────────────────────────────────────────────────────────────
        # 프로필 소스 결정
        # ─────────────────────────────────────────────────────────────
        # 우선순위:
        # 1. user_id가 있으면 → Qdrant에서 조회
        # 2. profile_text가 있으면 → 그대로 사용
        # 3. 둘 다 없으면 → 에러

        profile_text: str
        learning_goal: str
        absolute_level: str
        num_collected_words: int = 0
        num_weaknesses: int = 0
        num_completed_videos: int = 0

        if request.user_id is not None:
            # Case 1: Qdrant에서 프로필 조회
            profile_service = get_user_profile_service()
            profile = profile_service.get_profile(request.user_id)

            if profile is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"사용자 프로필을 찾을 수 없습니다: user_id={request.user_id}. "
                        f"먼저 POST /api/v1/user-profile/build로 프로필을 생성해주세요."
                    ),
                )

            profile_text = profile["profile_text"]
            metadata = profile["metadata"]
            learning_goal = metadata.get("learning_goal", "TRAVEL")
            absolute_level = metadata.get("absolute_level", "BEGINNER")
            num_collected_words = metadata.get("num_collected_words", 0)
            num_weaknesses = metadata.get("num_weaknesses", 0)
            num_completed_videos = metadata.get("num_completed_videos", 0)

            logger.info(f"프로필 로드 완료: user_id={request.user_id}")

        elif request.profile_text and request.learning_goal and request.absolute_level:
            # Case 2: 직접 전달 (테스트용)
            profile_text = request.profile_text
            learning_goal = request.learning_goal
            absolute_level = request.absolute_level

            logger.info("프로필 직접 전달 (테스트 모드)")

        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "user_id를 전달하거나, "
                    "profile_text + learning_goal + absolute_level을 모두 전달해야 합니다."
                ),
            )

        # ─────────────────────────────────────────────────────────────
        # LLM 호출: 검색어 생성
        # ─────────────────────────────────────────────────────────────

        generator = get_query_generator()
        result, tokens_used = await generator.generate(
            profile_text=profile_text,
            learning_goal=learning_goal,
            absolute_level=absolute_level,
            num_collected_words=num_collected_words,
            num_weaknesses=num_weaknesses,
            num_completed_videos=num_completed_videos,
        )

        # ─────────────────────────────────────────────────────────────
        # 응답 반환
        # ─────────────────────────────────────────────────────────────

        return GenerateQueryResponse(
            user_id=request.user_id,
            queries=result.queries,
            reasoning=result.reasoning,
            tokens_used=tokens_used,
            model=settings.openai_model_chat,
        )

    except HTTPException:
        # HTTPException은 그대로 재발생 (FastAPI가 처리)
        raise
    except Exception as e:
        logger.error(f"검색어 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))