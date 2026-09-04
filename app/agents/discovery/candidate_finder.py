"""
Candidate Finder - Content Discovery Agent 노드 2

역할:
- LLM이 생성한 검색어 5개로 YouTube 병렬 검색
- Redis 캐싱 활용 (24h TTL, 30일 룰 준수)
- 중복 제거 & 후보 영상 30~50개 확보

Agent 워크플로우에서의 위치:
    [Query Generator] → [Candidate Finder] → [Re-ranker]
                             ↑
                          여기!

성능 최적화:
- 병렬 처리 (asyncio.gather)
- 캐시 우선 조회
- 중복 제거 (video_id 기준)
"""

import asyncio
from typing import Any

from app.core.logger import logger
from app.services.redis_service import get_redis_service
from app.services.youtube_service import get_youtube_service


class CandidateFinderService:
    """
    YouTube 후보 영상 검색기
    
    처리 흐름:
    1. 검색어 5개 받기
    2. 각 검색어마다:
       - Redis 캐시 확인
       - Miss면 YouTube API 호출
       - 결과 캐싱 (24h)
    3. 모든 결과 통합
    4. 중복 제거 (video_id)
    5. 반환
    """

    def __init__(self):
        self.youtube = get_youtube_service()
        self.redis = get_redis_service()
        logger.info("🔎 CandidateFinderService 초기화 완료")

    async def find_candidates(
        self,
        queries: list[str],
        max_results_per_query: int = 10,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        검색어 리스트로 후보 영상 검색
        
        Args:
            queries: 검색어 리스트 (보통 5개)
            max_results_per_query: 검색어당 반환 개수
            force_refresh: True면 캐시 무시
        
        Returns:
            {
                "videos": [...],           # 중복 제거된 영상 리스트
                "total": int,              # 총 개수
                "cache_hits": int,         # 캐시 히트 수
                "cache_misses": int,       # API 호출 수
            }
        """
        logger.info(
            f"🔎 후보 영상 검색 시작: queries={len(queries)}, "
            f"per_query={max_results_per_query}, force_refresh={force_refresh}"
        )

        # ─────────────────────────────────────────────────────────────
        # 병렬로 모든 검색어 처리
        # ─────────────────────────────────────────────────────────────
        # asyncio.gather로 5개 검색을 동시에 실행
        # → 총 시간: max(각 검색어 시간) = 약 1~2초
        # → 순차 실행 대비 5배 빠름
        
        search_tasks = [
            self._search_with_cache(
                query=query,
                max_results=max_results_per_query,
                force_refresh=force_refresh,
            )
            for query in queries
        ]

        # 모든 검색 완료 대기
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # ─────────────────────────────────────────────────────────────
        # 결과 통합 & 중복 제거
        # ─────────────────────────────────────────────────────────────
        # 사용자가 중복된 영상을 여러 번 보지 않도록
        # video_id 기준으로 중복 제거
        
        all_videos: list[dict] = []
        video_ids_seen: set[str] = set()
        cache_hits = 0
        cache_misses = 0

        for query, result in zip(queries, results):
            # 에러 처리
            if isinstance(result, Exception):
                logger.error(f"❌ 검색 실패: query='{query}', error={result}")
                cache_misses += 1
                continue

            # 캐시 히트/미스 카운트
            if result["from_cache"]:
                cache_hits += 1
            else:
                cache_misses += 1

            # 영상 추가 (중복 제거)
            for video in result["videos"]:
                video_id = video["video_id"]
                if video_id not in video_ids_seen:
                    video_ids_seen.add(video_id)
                    # 어떤 검색어로 매칭됐는지 기록
                    video["matched_query"] = query
                    all_videos.append(video)

        logger.info(
            f"✅ 후보 영상 검색 완료: total={len(all_videos)}, "
            f"cache_hits={cache_hits}, cache_misses={cache_misses}"
        )

        return {
            "videos": all_videos,
            "total": len(all_videos),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        }

    async def _search_with_cache(
        self,
        query: str,
        max_results: int,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        캐시 우선 검색 (내부 메서드)
        
        전략:
        1. force_refresh가 True면 캐시 스킵
        2. Redis 캐시 조회
        3. Miss면 YouTube API 호출
        4. 결과 캐싱 후 반환
        """
        # ─────────────────────────────────────────────────────────────
        # Step 1: 캐시 조회 (force_refresh가 False일 때만)
        # ─────────────────────────────────────────────────────────────
        
        if not force_refresh:
            cached = await self.redis.get_youtube_search(query)
            if cached is not None:
                logger.debug(f"📺 캐시 HIT: query='{query}', count={len(cached)}")
                return {
                    "videos": cached[:max_results],  # 요청 개수만큼만
                    "from_cache": True,
                }

        # ─────────────────────────────────────────────────────────────
        # Step 2: YouTube API 호출 (Cache Miss 또는 강제 갱신)
        # ─────────────────────────────────────────────────────────────
        # 
        # 주의: YouTube API는 동기 함수라서 
        # asyncio.to_thread로 감싸서 비동기 컨텍스트에서 실행
        # → 다른 요청 블로킹 방지
        
        logger.debug(f"🌐 YouTube API 호출: query='{query}'")
        
        try:
            videos = await asyncio.to_thread(
                self.youtube.search_videos,
                query=query,
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"❌ YouTube 검색 실패: query='{query}', error={e}")
            return {"videos": [], "from_cache": False}

        # ─────────────────────────────────────────────────────────────
        # Step 3: 결과 캐싱 (24h TTL, 30일 룰 준수)
        # ─────────────────────────────────────────────────────────────
        
        if videos:
            await self.redis.set_youtube_search(query, videos)

        return {
            "videos": videos,
            "from_cache": False,
        }


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_candidate_finder: CandidateFinderService | None = None


def get_candidate_finder() -> CandidateFinderService:
    """CandidateFinderService 싱글톤 반환"""
    global _candidate_finder
    if _candidate_finder is None:
        _candidate_finder = CandidateFinderService()
    return _candidate_finder