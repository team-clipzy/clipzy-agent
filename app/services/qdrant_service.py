"""
Qdrant Vector DB 서비스
영상 임베딩과 사용자 임베딩을 관리합니다.
"""

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.core.logger import logger


class QdrantService:
    """Qdrant 클라이언트 래퍼"""

    # OpenAI text-embedding-3-small의 임베딩 차원
    EMBEDDING_DIM = 1536

    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        logger.info(
            f"🔌 Qdrant 클라이언트 초기화: "
            f"{settings.qdrant_host}:{settings.qdrant_port}"
        )

    def health_check(self) -> bool:
        """Qdrant 연결 상태 확인"""
        try:
            collections = self.client.get_collections()
            logger.info(
                f"✅ Qdrant 연결 성공. 현재 컬렉션: "
                f"{[c.name for c in collections.collections]}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Qdrant 연결 실패: {e}")
            return False

    def ensure_collections(self) -> None:
        """
        필요한 컬렉션이 없으면 생성합니다.
        - clipzy_videos: 영상 임베딩
        - clipzy_users: 사용자 임베딩
        """
        collection_names = [
            settings.qdrant_collection_video,
            settings.qdrant_collection_user,
        ]

        existing = {c.name for c in self.client.get_collections().collections}

        for name in collection_names:
            if name in existing:
                logger.info(f"✓ 컬렉션 이미 존재: {name}")
                continue

            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.EMBEDDING_DIM,
                    distance=Distance.COSINE,  # 코사인 유사도
                ),
            )
            logger.info(f"✨ 컬렉션 생성 완료: {name}")

    def get_collection_info(self, name: str) -> dict[str, Any]:
        """컬렉션 정보 조회"""
        info = self.client.get_collection(name)
        return {
            "name": name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }


# 싱글톤 인스턴스
_qdrant_service: QdrantService | None = None


def get_qdrant_service() -> QdrantService:
    """QdrantService 싱글톤 반환"""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service