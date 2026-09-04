"""
Redis 캐싱 서비스

역할:
- YouTube 검색 결과 24시간 캐싱
- LLM 응답 캐싱 (선택)
- 30일 룰 자동 준수 (TTL 24h)

캐시 전략:
- Key 규칙: "prefix:hash_or_id"
- TTL: 24시간 (86400초)
- 만료 시 자동 삭제 (LRU)

예시 캐시 키:
- youtube_search:hash("beginner travel english") → 검색 결과 리스트
- user_profile_cache:user_id_1 → 프로필 데이터 (선택)
"""

import hashlib
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logger import logger


class RedisService:
    """
    Redis 클라이언트 래퍼 (비동기)
    
    사용 이유:
    - YouTube API quota 절약 (같은 검색어 재사용)
    - 응답 속도 향상 (수백 ms → 수 ms)
    - 정책 준수 (24h TTL로 30일 룰 자동)
    
    async/await 사용:
    - FastAPI가 비동기 프레임워크
    - Redis 호출 중 다른 요청 처리 가능
    - 성능 최적화
    """

    # 캐시 TTL (초)
    DEFAULT_TTL = 86400  # 24시간
    SHORT_TTL = 3600     # 1시간
    LONG_TTL = 604800    # 7일 (파생 지표용)

    def __init__(self):
        """Redis 클라이언트 초기화"""
        self.client: redis.Redis = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,  # 응답을 자동으로 str로 디코딩
        )
        logger.info(f"🔴 Redis 클라이언트 초기화: {settings.redis_url}")

    async def health_check(self) -> bool:
        """
        Redis 연결 상태 확인
        
        Returns:
            연결 성공 여부
        """
        try:
            pong = await self.client.ping()
            logger.info(f"✅ Redis 연결 정상: {pong}")
            return True
        except Exception as e:
            logger.error(f"❌ Redis 연결 실패: {e}")
            return False

    # =========================================================================
    # 기본 캐시 메서드
    # =========================================================================

    async def get(self, key: str) -> Any | None:
        """
        캐시에서 값 조회
        
        Args:
            key: 캐시 키
        
        Returns:
            저장된 값 (JSON 파싱됨) 또는 None (없음)
        """
        try:
            value = await self.client.get(key)
            if value is None:
                logger.debug(f"🔍 캐시 MISS: key={key}")
                return None

            # JSON 자동 파싱
            parsed = json.loads(value)
            logger.debug(f"✨ 캐시 HIT: key={key}")
            return parsed

        except json.JSONDecodeError:
            # JSON이 아니면 문자열 그대로 반환
            logger.warning(f"⚠️ JSON 파싱 실패, 원본 반환: key={key}")
            return value
        except Exception as e:
            logger.error(f"❌ 캐시 조회 실패: key={key}, error={e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        캐시에 값 저장 (TTL 자동 설정)
        
        Args:
            key: 캐시 키
            value: 저장할 값 (JSON 직렬화 가능해야 함)
            ttl: 만료 시간 (초, 기본 24시간)
        
        Returns:
            저장 성공 여부
        """
        try:
            # JSON 자동 직렬화
            serialized = json.dumps(value, ensure_ascii=False)

            await self.client.setex(
                name=key,
                time=ttl,
                value=serialized,
            )
            logger.debug(f"💾 캐시 저장: key={key}, ttl={ttl}s")
            return True

        except Exception as e:
            logger.error(f"❌ 캐시 저장 실패: key={key}, error={e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        캐시 삭제
        
        Args:
            key: 삭제할 캐시 키
        
        Returns:
            삭제 성공 여부
        """
        try:
            result = await self.client.delete(key)
            logger.info(f"🗑 캐시 삭제: key={key}, deleted={result}")
            return result > 0
        except Exception as e:
            logger.error(f"❌ 캐시 삭제 실패: key={key}, error={e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        캐시 키 존재 여부 확인
        
        Args:
            key: 캐시 키
        
        Returns:
            존재 여부
        """
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"❌ 캐시 존재 확인 실패: key={key}, error={e}")
            return False

    # =========================================================================
    # YouTube 검색 결과 전용 메서드
    # =========================================================================

    @staticmethod
    def make_search_key(query: str) -> str:
        """
        검색어를 캐시 키로 변환
        
        왜 해시를 사용?
        - 검색어에 특수문자, 공백 등이 있어도 안전한 키 생성
        - 키 길이 통일 (Redis 성능 향상)
        - 대소문자 정규화
        
        예시:
        "Beginner Travel English" 
            ↓
        "youtube_search:a1b2c3d4e5f6..."
        """
        # 소문자 + 공백 정규화
        normalized = query.lower().strip()
        
        # MD5 해시 (16자로 축약)
        hash_obj = hashlib.md5(normalized.encode())
        hash_short = hash_obj.hexdigest()[:16]
        
        return f"youtube_search:{hash_short}"

    async def get_youtube_search(self, query: str) -> list[dict] | None:
        """
        캐시된 YouTube 검색 결과 조회
        
        Args:
            query: 검색어
        
        Returns:
            영상 리스트 (캐시된 경우) 또는 None
        """
        key = self.make_search_key(query)
        result = await self.get(key)
        
        if result is not None:
            logger.info(f"📺 YouTube 캐시 HIT: query='{query}'")
        
        return result

    async def set_youtube_search(
        self,
        query: str,
        videos: list[dict],
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        YouTube 검색 결과 캐싱
        
        Args:
            query: 검색어
            videos: 영상 리스트
            ttl: TTL (기본 24시간, 30일 룰 준수)
        
        Returns:
            저장 성공 여부
        """
        key = self.make_search_key(query)
        success = await self.set(key, videos, ttl=ttl)
        
        if success:
            logger.info(
                f"📺 YouTube 결과 캐싱: query='{query}', "
                f"count={len(videos)}, ttl={ttl}s"
            )
        
        return success

    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================

    async def clear_pattern(self, pattern: str) -> int:
        """
        패턴에 매칭되는 모든 키 삭제 (개발용)
        
        Args:
            pattern: 삭제할 키 패턴 (예: "youtube_search:*")
        
        Returns:
            삭제된 키 개수
        
        ⚠️ 프로덕션에서는 사용 주의 (성능 영향)
        """
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if not keys:
                logger.info(f"삭제할 키 없음: pattern={pattern}")
                return 0

            deleted = await self.client.delete(*keys)
            logger.warning(f"⚠️ 패턴 매칭 삭제: pattern={pattern}, deleted={deleted}")
            return deleted

        except Exception as e:
            logger.error(f"❌ 패턴 삭제 실패: pattern={pattern}, error={e}")
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """
        Redis 통계 조회 (개발/모니터링용)
        
        Returns:
            사용량, 키 개수 등 통계 정보
        """
        try:
            info = await self.client.info("stats")
            memory_info = await self.client.info("memory")
            db_size = await self.client.dbsize()

            return {
                "total_keys": db_size,
                "used_memory_human": memory_info.get("used_memory_human", "N/A"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
            }
        except Exception as e:
            logger.error(f"❌ Redis 통계 조회 실패: {e}")
            return {}

    @staticmethod
    def _calculate_hit_rate(info: dict) -> str:
        """캐시 히트율 계산"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses

        if total == 0:
            return "N/A"
        
        rate = (hits / total) * 100
        return f"{rate:.2f}%"

    async def close(self) -> None:
        """Redis 연결 종료"""
        await self.client.close()
        logger.info("👋 Redis 연결 종료")


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================
# 왜 싱글톤?
# - Redis 커넥션 풀 재사용 (성능)
# - 매번 초기화 방지
# - 메모리 절약

_redis_service: RedisService | None = None


def get_redis_service() -> RedisService:
    """RedisService 싱글톤 반환"""
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService()
    return _redis_service