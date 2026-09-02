"""
Qdrant Vector DB 서비스
사용자 프로필 임베딩을 관리합니다.
"""

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.core.logger import logger


class QdrantService:
    """Qdrant 클라이언트 래퍼"""

    EMBEDDING_DIM = 1536  # text-embedding-3-small

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
        """필요한 컬렉션이 없으면 생성"""
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
                    distance=Distance.COSINE,
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

    def upsert_point(
        self,
        collection_name: str,
        embedding: list[float],
        payload: dict[str, Any],
        point_id: str | int | None = None,
    ) -> str:
        """
        Qdrant에 벡터 + 메타데이터 저장

        Args:
            collection_name: 컬렉션 이름
            embedding: 임베딩 벡터
            payload: 저장할 메타데이터
            point_id: 포인트 ID (없으면 UUID 자동 생성)

        Returns:
            저장된 포인트 ID
        """
        if point_id is None:
            point_id = str(uuid.uuid4())

        self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
        logger.info(
            f"💾 벡터 저장 완료: collection={collection_name}, id={point_id}"
        )
        return str(point_id)

    def upsert_batch(
        self,
        collection_name: str,
        embeddings: list[list[float]],
        payloads: list[dict[str, Any]],
        ids: list[str | int] | None = None,
    ) -> list[str]:
        """여러 벡터를 배치로 저장"""
        if len(embeddings) != len(payloads):
            raise ValueError("embeddings와 payloads 개수가 다릅니다")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in embeddings]

        points = [
            PointStruct(id=pid, vector=vec, payload=pl)
            for pid, vec, pl in zip(ids, embeddings, payloads)
        ]

        self.client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.info(
            f"💾 배치 저장 완료: collection={collection_name}, count={len(points)}"
        )
        return [str(pid) for pid in ids]

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 5,
        filter_condition: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        유사도 검색

        Args:
            collection_name: 검색할 컬렉션 이름
            query_vector: 쿼리 벡터
            top_k: 반환할 결과 개수
            filter_condition: Qdrant 필터 조건 (선택)

        Returns:
            검색 결과 리스트
        """
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_condition,
        )

        logger.info(
            f"🔍 검색 완료: collection={collection_name}, "
            f"results={len(results)}"
        )

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload or {},
            }
            for r in results
        ]

    def delete_point(self, collection_name: str, point_id: str | int) -> None:
        """포인트 삭제"""
        self.client.delete(
            collection_name=collection_name,
            points_selector=[point_id],
        )
        logger.info(f"🗑 포인트 삭제: collection={collection_name}, id={point_id}")

    def clear_collection(self, collection_name: str) -> None:
        """컬렉션의 모든 데이터 삭제 (개발용)"""
        self.client.delete_collection(collection_name)
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        logger.warning(f"⚠️  컬렉션 초기화: {collection_name}")


# 싱글톤 인스턴스
_qdrant_service: QdrantService | None = None


def get_qdrant_service() -> QdrantService:
    """QdrantService 싱글톤 반환"""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service