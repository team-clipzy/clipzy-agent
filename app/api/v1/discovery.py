"""
Content Discovery Agent - 통합 API

역할:
- Query Generator + Candidate Finder를 조합한 엔드포인트
- 사용자 요청 → 검색어 생성 → YouTube 검색 → 결과 반환

이게 진짜 Agent의 시작:
    사용자: "추천 영상 줘"
        ↓
    Agent가 알아서:
        1. 프로필 분석
        2. 검색어 생성
        3. YouTube 검색
        4. 결과 반환
"""

import time

from fastapi import APIRouter, HTTPException

from app.agents.discovery.candidate_finder import get_candidate_finder
from app.agents.discovery.query_generator import get_query_generator
from app.core.logger import logger
from app.schemas.discovery import (
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    VideoCandidate,
)
from app.services.user_profile_service import get_user_profile_service

router = APIRouter(prefix="/discovery", tags=["Content Discovery"])


@router.post(
    "/search",
    response_model=DiscoverySearchResponse,
    summary="사용자 맞춤 콘텐츠 발견 (Agent 통합)",
)
async def discover_content(request: DiscoverySearchRequest) -> DiscoverySearchResponse:
    """
    사용자 프로필 기반 YouTube 영상 자동 검색

    **처리 흐름:**
    ```
    1. 사용자 프로필 로드 (Qdrant)
    2. LLM으로 검색어 5개 생성 (gpt-4o-mini)
    3. 각 검색어로 YouTube 병렬 검색
       - Redis 캐시 우선 조회 (24h TTL)
       - Miss 시 API 호출
    4. 중복 제거 & 통합
    5. 후보 영상 30~50개 반환
    ```

    **성능:**
    - 캐시 히트 시: 1~2초
    - 캐시 미스 시: 3~5초 (YouTube API 호출)

    **비용:**
    - LLM: 약 $0.0002 (0.03원)
    - YouTube API: 500 units (일일 quota의 5%)

    **정책 준수:**
    - 공식 YouTube API만 사용
    - 24h Redis 캐싱 (30일 룰 자동 준수)
    - 자막 저장 X
    """
    start_time = time.time()

    try:
        # =====================================================================
        # Step 1: 사용자 프로필 로드
        # =====================================================================
        # Qdrant에서 사용자 프로필 벡터 & 메타데이터 조회
        # 프로필이 없으면 404 (먼저 프로필 생성 필요)

        logger.info(f"🎯 Discovery 요청 시작: user_id={request.user_id}")

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

        logger.info(f"✅ 프로필 로드 완료: user_id={request.user_id}")

        # =====================================================================
        # Step 2: LLM으로 검색어 5개 생성
        # =====================================================================
        # gpt-4o-mini가 사용자 프로필을 분석해
        # 개인 맞춤 YouTube 검색어 5개 생성
        # 다양성 규칙 적용 (5가지 각도)

        query_generator = get_query_generator()
        generated, tokens_used = await query_generator.generate(
            profile_text=profile_text,
            learning_goal=metadata.get("learning_goal", "TRAVEL"),
            absolute_level=metadata.get("absolute_level", "BEGINNER"),
            num_collected_words=metadata.get("num_collected_words", 0),
            num_weaknesses=metadata.get("num_weaknesses", 0),
            num_completed_videos=metadata.get("num_completed_videos", 0),
        )

        logger.info(
            f"✅ 검색어 생성 완료: queries={len(generated.queries)}, "
            f"tokens={tokens_used}"
        )

        # =====================================================================
        # Step 3: YouTube 병렬 검색 (Redis 캐싱 포함)
        # =====================================================================
        # 5개 검색어를 asyncio.gather로 동시 실행
        # 각 검색어마다:
        #   - Redis 캐시 확인
        #   - Miss면 YouTube API 호출
        #   - 결과 24h TTL로 캐싱

        finder = get_candidate_finder()
        search_result = await finder.find_candidates(
            queries=generated.queries,
            max_results_per_query=request.max_videos_per_query,
            force_refresh=request.force_refresh,
        )

        # =====================================================================
        # Step 4: 응답 포맷팅
        # =====================================================================
        # YouTube API 결과를 우리 스키마에 맞게 변환

        video_candidates = [
            VideoCandidate(
                video_id=video["video_id"],
                title=video["title"],
                description=video["description"][:200],  # 설명 200자 제한
                channel_id=video["channel_id"],
                channel_name=video["channel_name"],
                thumbnail_url=video["thumbnail_url"],
                published_at=video["published_at"],
                matched_query=video["matched_query"],
            )
            for video in search_result["videos"]
        ]

        # 처리 시간 계산
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"🎉 Discovery 완료: user_id={request.user_id}, "
            f"videos={len(video_candidates)}, "
            f"time={processing_time_ms}ms, "
            f"cache_hits={search_result['cache_hits']}/{len(generated.queries)}"
        )

        return DiscoverySearchResponse(
            user_id=request.user_id,
            generated_queries=generated.queries,
            query_reasoning=generated.reasoning,
            total_candidates=search_result["total"],
            videos=video_candidates,
            cache_hits=search_result["cache_hits"],
            cache_misses=search_result["cache_misses"],
            processing_time_ms=processing_time_ms,
            tokens_used=tokens_used,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Discovery 실패: user_id={request.user_id}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/cache/stats",
    summary="Redis 캐시 통계 조회 (개발용)",
)
async def get_cache_stats() -> dict:
    """
    Redis 캐시 상태 조회

    - 총 키 개수
    - 메모리 사용량
    - 히트율
    - 총 처리 명령어 수
    """
    from app.services.redis_service import get_redis_service

    redis_service = get_redis_service()
    stats = await redis_service.get_stats()

    return {
        "status": "success",
        "stats": stats,
    }


@router.delete(
    "/cache/clear",
    summary="YouTube 검색 캐시 초기화 (개발용)",
)
async def clear_search_cache() -> dict:
    """
    YouTube 검색 결과 캐시 모두 삭제

    ⚠️ 개발 환경에서만 사용!
    - 프로덕션에서는 quota 낭비
    - 캐시는 24h TTL로 자동 만료됨
    """
    from app.core.config import settings
    from app.services.redis_service import get_redis_service

    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="개발 환경에서만 사용 가능합니다",
        )

    redis_service = get_redis_service()
    deleted = await redis_service.clear_pattern("youtube_search:*")

    return {
        "status": "success",
        "deleted_keys": deleted,
        "message": f"{deleted}개의 캐시 키가 삭제되었습니다",
    }
    
# ============================================================================
# 최종 추천 API (Re-ranker 포함)
# ============================================================================

from app.agents.discovery.reranker import get_reranker
from app.schemas.recommendation import (
    RecommendedVideo,
    RecommendRequest,
    RecommendResponse,
)


@router.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="사용자 맞춤 Top 6 영상 추천 (완전한 Agent)",
)
async def recommend_videos(request: RecommendRequest) -> RecommendResponse:
    """
    사용자에게 맞춤 Top 6 YouTube 영상 추천 (완전한 AI Agent)

    **처리 흐름:**
    ```
    1. 사용자 프로필 로드 (Qdrant)
    2. LLM 검색어 5개 생성 (gpt-4o-mini)
    3. YouTube 병렬 검색 + Redis 캐싱 (47개 후보)
    4. LLM Re-ranker로 Top 6 선정 + 한국어 이유 생성
    5. 최종 응답 반환
    ```

    **결과:**
    - 6개 개인화 추천 영상
    - 각 영상마다 한국어 추천 이유
    - 전체 추천 전략 설명

    **성능:**
    - 캐시 미스: 6-8초
    - 캐시 히트: 3-4초

    **비용:**
    - LLM Query Gen: ~\$0.0002
    - LLM Re-ranker: ~\$0.001
    - 총: 약 $0.0012 (0.15원)

    **활용 예시 (프론트엔드):**
    - 완주 영상 없음: 6개 다 표시
    - 완주 영상 있음: 5개만 사용 (마스터리 배지 자리 확보)
    """
    import time
    start_time = time.time()

    try:
        # =====================================================================
        # Step 1: 사용자 프로필 로드
        # =====================================================================
        
        logger.info(f"🎯 Recommend 요청 시작: user_id={request.user_id}")

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

        # =====================================================================
        # Step 2: LLM 검색어 생성
        # =====================================================================
        
        query_generator = get_query_generator()
        generated, tokens_query = await query_generator.generate(
            profile_text=profile_text,
            learning_goal=metadata.get("learning_goal", "TRAVEL"),
            absolute_level=metadata.get("absolute_level", "BEGINNER"),
            num_collected_words=metadata.get("num_collected_words", 0),
            num_weaknesses=metadata.get("num_weaknesses", 0),
            num_completed_videos=metadata.get("num_completed_videos", 0),
        )

        logger.info(f"✅ 검색어 생성 완료: queries={len(generated.queries)}")

        # =====================================================================
        # Step 3: YouTube 병렬 검색 (Redis 캐싱)
        # =====================================================================
        
        finder = get_candidate_finder()
        search_result = await finder.find_candidates(
            queries=generated.queries,
            max_results_per_query=request.max_videos_per_query,
            force_refresh=request.force_refresh,
        )

        candidates = search_result["videos"]
        logger.info(f"✅ 후보 확보: {len(candidates)}개")

        # 후보가 6개 미만이면 에러
        if len(candidates) < 6:
            raise HTTPException(
                status_code=500,
                detail=f"후보 영상이 부족합니다 ({len(candidates)}개). YouTube API 상태를 확인해주세요.",
            )

        # =====================================================================
        # Step 4: LLM Re-ranker
        # =====================================================================
        # 
        # 47개 후보 → Top 6 선정
        # 각 영상마다 한국어 추천 이유 생성
        
        # 메타데이터에서 상세 정보 추출
        # (Qdrant에는 요약된 count만 저장되어 있음)
        # TODO: 프로덕션에서는 Spring DB에서 상세 정보 조회
        # 지금은 프로필 텍스트만 사용
        
        reranker = get_reranker()
        rerank_result, tokens_rerank = await reranker.rerank(
            profile_text=profile_text,
            learning_goal=metadata.get("learning_goal", "TRAVEL"),
            absolute_level=metadata.get("absolute_level", "BEGINNER"),
            weaknesses=[],       # TODO: Spring에서 조회
            weak_words=[],       # TODO: Spring에서 조회
            collected_words=[],  # TODO: Spring에서 조회
            candidates=candidates,
        )

        logger.info(f"✅ Re-rank 완료: top_6 선정")

        # =====================================================================
        # Step 5: 응답 조립
        # =====================================================================
        # 
        # LLM이 선정한 video_id를 실제 영상 정보와 매칭
        # 후보 리스트에서 찾아서 완전한 정보 구성
        
        # video_id로 빠른 조회를 위한 딕셔너리
        candidates_by_id = {c["video_id"]: c for c in candidates}
        
        recommendations = []
        for ranked in rerank_result.recommendations:
            candidate = candidates_by_id.get(ranked.video_id)
            if not candidate:
                logger.warning(f"⚠️ 매칭 실패: {ranked.video_id}")
                continue
            
            recommendations.append(RecommendedVideo(
                rank=ranked.rank,
                reason=ranked.reason,
                video_id=candidate["video_id"],
                title=candidate["title"],
                description=candidate["description"][:200],  # 200자 제한
                channel_id=candidate["channel_id"],
                channel_name=candidate["channel_name"],
                thumbnail_url=candidate["thumbnail_url"],
                published_at=candidate["published_at"],
                matched_query=candidate.get("matched_query", ""),
            ))

        # 순위별 정렬 (안전장치)
        recommendations.sort(key=lambda x: x.rank)

        # =====================================================================
        # 최종 응답
        # =====================================================================
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # 비용 계산
        total_tokens = tokens_query + tokens_rerank
        total_cost = (total_tokens / 1_000_000) * 0.30  # gpt-4o-mini 평균

        logger.info(
            f"🎉 Recommend 완료: user_id={request.user_id}, "
            f"top={len(recommendations)}, "
            f"time={processing_time_ms}ms, "
            f"cost=${total_cost:.6f}"
        )

        return RecommendResponse(
            user_id=request.user_id,
            recommendations=recommendations,
            overall_strategy=rerank_result.overall_strategy,
            generated_queries=generated.queries,
            total_candidates=len(candidates),
            cache_hits=search_result["cache_hits"],
            cache_misses=search_result["cache_misses"],
            processing_time_ms=processing_time_ms,
            tokens_used_query=tokens_query,
            tokens_used_rerank=tokens_rerank,
            total_cost_usd=total_cost,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Recommend 실패: user_id={request.user_id}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))
            