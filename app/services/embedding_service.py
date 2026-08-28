"""
OpenAI 임베딩 서비스
텍스트를 벡터로 변환합니다.
"""

from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logger import logger


class EmbeddingService:
    """OpenAI Embedding API 래퍼"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model_embedding
        logger.info(f"🧠 EmbeddingService 초기화 (model: {self.model})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed(self, text: str) -> list[float]:
        """
        단일 텍스트를 임베딩 벡터로 변환

        Args:
            text: 임베딩할 텍스트

        Returns:
            1536차원 벡터 (text-embedding-3-small 기준)

        Raises:
            openai.APIError: API 호출 실패 시
        """
        if not text or not text.strip():
            raise ValueError("텍스트가 비어있습니다")

        # 개행 문자 제거 (임베딩 품질 향상)
        text = text.replace("\n", " ").strip()

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        embedding = response.data[0].embedding
        logger.debug(
            f"✨ 임베딩 완료: len={len(text)} chars, "
            f"tokens={response.usage.total_tokens}"
        )
        return embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        여러 텍스트를 한 번에 임베딩 (배치 처리 - 비용 절감)

        Args:
            texts: 임베딩할 텍스트 리스트 (최대 2048개, 권장 100개)

        Returns:
            벡터 리스트
        """
        if not texts:
            raise ValueError("텍스트 리스트가 비어있습니다")

        # 전처리
        cleaned = [t.replace("\n", " ").strip() for t in texts if t.strip()]

        if not cleaned:
            raise ValueError("유효한 텍스트가 없습니다")

        response = await self.client.embeddings.create(
            model=self.model,
            input=cleaned,
        )

        embeddings = [item.embedding for item in response.data]
        logger.info(
            f"✨ 배치 임베딩 완료: count={len(embeddings)}, "
            f"tokens={response.usage.total_tokens}"
        )
        return embeddings

    def get_dimension(self) -> int:
        """임베딩 벡터의 차원 수 반환"""
        # text-embedding-3-small: 1536
        # text-embedding-3-large: 3072
        # text-embedding-ada-002: 1536
        return 1536


# 싱글톤 인스턴스
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """EmbeddingService 싱글톤 반환"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service