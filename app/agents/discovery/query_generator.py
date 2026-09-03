"""
LLM Query Generator - Content Discovery Agent 노드 1

역할:
- 사용자 프로필을 분석해 YouTube 검색어 5개 자동 생성
- Rule-based가 아닌 LLM 기반으로 개인화된 검색어 생성
- Structured Output(JSON)으로 안정적인 파싱

Agent 워크플로우에서의 위치:
    [User Profile] → [Query Generator] → [YouTube Search] → [Re-ranker]
                          ↑
                       여기!
"""

import json

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.discovery.prompts import (
    QUERY_GENERATOR_SYSTEM_PROMPT,
    QUERY_GENERATOR_USER_TEMPLATE,
)
from app.core.config import settings
from app.core.logger import logger
from app.schemas.query import GeneratedQueries


class QueryGeneratorService:
    """
    사용자 프로필 기반 YouTube 검색어 생성기
    
    사용 모델: gpt-4o-mini
    - 이유: 검색어 생성은 창의성보다 정확성이 중요
    - 비용: gpt-4o의 1/10 수준
    - 속도: 빠른 응답 (평균 1-2초)
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model_chat  # gpt-4o-mini
        logger.info(f"🧠 QueryGeneratorService 초기화 (model: {self.model})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(
        self,
        profile_text: str,
        learning_goal: str = "TRAVEL",
        absolute_level: str = "BEGINNER",
        num_collected_words: int = 0,
        num_weaknesses: int = 0,
        num_completed_videos: int = 0,
    ) -> tuple[GeneratedQueries, int]:
        """
        사용자 프로필로 검색어 5개 생성
        
        Args:
            profile_text: 자연어 프로필 (build_profile_text 결과)
            learning_goal: 학습 목표 (TRAVEL/DAILY/BUSINESS)
            absolute_level: 영어 수준 (BEGINNER/INTERMEDIATE/ADVANCED)
            num_collected_words: 수집 단어 수
            num_weaknesses: 약점 표현 수
            num_completed_videos: 완주 영상 수
        
        Returns:
            (GeneratedQueries, 사용된 토큰 수)
        
        재시도 정책:
            - 최대 3회 시도
            - Exponential Backoff (2초, 4초, 8초)
            - API 일시적 장애 대응
        """
        
        # ─────────────────────────────────────────────────────────────
        # 프롬프트 조립
        # ─────────────────────────────────────────────────────────────
        # System Prompt: LLM의 역할과 규칙 정의
        # User Prompt: 실제 사용자 데이터 전달
        
        user_message = QUERY_GENERATOR_USER_TEMPLATE.format(
            profile_text=profile_text,
            learning_goal=learning_goal,
            absolute_level=absolute_level,
            num_collected_words=num_collected_words,
            num_weaknesses=num_weaknesses,
            num_completed_videos=num_completed_videos,
        )

        logger.debug(f"프롬프트 조립 완료: user_message_length={len(user_message)}")

        # ─────────────────────────────────────────────────────────────
        # OpenAI API 호출
        # ─────────────────────────────────────────────────────────────
        # response_format={"type": "json_object"}:
        #   - LLM이 반드시 JSON으로 응답하도록 강제
        #   - 파싱 실패 리스크 최소화
        # 
        # temperature=0.7:
        #   - 0.0 = 결정적 (매번 같은 답)
        #   - 1.0 = 창의적 (매번 다른 답)
        #   - 0.7 = 적당한 다양성 (검색어에 적합)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": QUERY_GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=500,  # 검색어 5개 + reasoning에 충분
        )

        # ─────────────────────────────────────────────────────────────
        # 응답 파싱 & 검증
        # ─────────────────────────────────────────────────────────────
        # Pydantic이 자동으로:
        # 1. queries 개수 검증 (정확히 5개)
        # 2. reasoning 존재 여부 검증
        # 3. 타입 검증 (list[str], str)

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("LLM이 빈 응답을 반환했습니다")

        try:
            parsed_json = json.loads(raw_content)
            result = GeneratedQueries(**parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {raw_content}")
            raise ValueError(f"LLM 응답이 유효한 JSON이 아닙니다: {e}") from e

        # ─────────────────────────────────────────────────────────────
        # 토큰 사용량 추적 (비용 관리)
        # ─────────────────────────────────────────────────────────────
        # gpt-4o-mini 가격 (2025년 기준):
        #   - Input:  $0.150 / 1M tokens
        #   - Output: $0.600 / 1M tokens
        # 
        # 검색어 생성 1회 예상:
        #   - Input: ~500 tokens (프롬프트 + 프로필)
        #   - Output: ~200 tokens (검색어 + reasoning)
        #   - 비용: 약 $0.0002 (0.03원)

        tokens_used = response.usage.total_tokens

        logger.info(
            f"검색어 생성 완료: "
            f"queries={len(result.queries)}, "
            f"tokens={tokens_used}, "
            f"cost=${(tokens_used / 1_000_000) * 0.3:.6f}"
        )

        return result, tokens_used


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================
# 왜 싱글톤?
# - AsyncOpenAI 클라이언트 재사용 (커넥션 풀 유지)
# - 매번 초기화 방지 (성능 개선)
# - 메모리 절약

_query_generator: QueryGeneratorService | None = None


def get_query_generator() -> QueryGeneratorService:
    """QueryGeneratorService 싱글톤 반환"""
    global _query_generator
    if _query_generator is None:
        _query_generator = QueryGeneratorService()
    return _query_generator