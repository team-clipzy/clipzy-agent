"""
LLM Re-ranker - Content Discovery Agent 노드 4

역할:
- 47개 후보 영상 → Top 6 선정
- 개인화된 순위 매기기
- 한국어 추천 이유 생성

Agent 워크플로우 위치:
    [Query Gen] → [Candidate Finder] → [Re-ranker] → [최종 응답]
                                            ↑
                                         여기!

성능:
- 응답 시간: 2-4초 (후보 개수에 비례)
- 토큰: 2000-3000 (후보 리스트 포함)
- 비용: ~$0.001 (약 1.5원)
"""

import json
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.discovery.rerank_prompts import (
    RERANKER_SYSTEM_PROMPT,
    RERANKER_USER_TEMPLATE,
)
from app.core.config import settings
from app.core.logger import logger
from app.schemas.recommendation import RerankerOutput


class RerankerService:
    """
    LLM 기반 영상 재정렬 서비스
    
    사용 모델: gpt-4o-mini
    - 이유: 판단 작업이지만 창의성보다 정확성
    - 비용: 후보 47개 포함해도 저렴
    - 속도: 2-4초로 사용자 대기 가능
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model_chat
        logger.info(f"🎯 RerankerService 초기화 (model: {self.model})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def rerank(
        self,
        profile_text: str,
        learning_goal: str,
        absolute_level: str,
        weaknesses: list[dict],
        weak_words: list[dict],
        collected_words: list[dict],
        candidates: list[dict],
    ) -> tuple[RerankerOutput, int]:
        """
        후보 영상들을 재정렬해 Top 6 선정
        
        Args:
            profile_text: 자연어 프로필
            learning_goal: 학습 목표
            absolute_level: 영어 수준
            weaknesses: 약점 표현 리스트
            weak_words: 취약 단어 리스트
            collected_words: 수집 단어 리스트
            candidates: 후보 영상 리스트 (47개)
        
        Returns:
            (RerankerOutput, 사용된 토큰 수)
        """
        # ─────────────────────────────────────────────────────────────
        # 컨텍스트 요약 (LLM에 명확히 전달)
        # ─────────────────────────────────────────────────────────────
        
        weaknesses_summary = self._summarize_weaknesses(weaknesses)
        weak_words_summary = self._summarize_weak_words(weak_words)
        collected_words_summary = self._summarize_collected_words(collected_words)
        candidates_list = self._format_candidates(candidates)

        # ─────────────────────────────────────────────────────────────
        # 프롬프트 조립
        # ─────────────────────────────────────────────────────────────
        
        user_message = RERANKER_USER_TEMPLATE.format(
            profile_text=profile_text,
            learning_goal=learning_goal,
            absolute_level=absolute_level,
            weaknesses_summary=weaknesses_summary,
            weak_words_summary=weak_words_summary,
            collected_words_summary=collected_words_summary,
            total_candidates=len(candidates),
            candidates_list=candidates_list,
        )

        logger.debug(f"Reranker 프롬프트 크기: {len(user_message)} chars")

        # ─────────────────────────────────────────────────────────────
        # OpenAI API 호출
        # ─────────────────────────────────────────────────────────────
        # temperature=0.3:
        #   - 창의성보다 일관성 중시
        #   - 사용자에게 안정적 추천
        # 
        # max_tokens=1500:
        #   - Top 6 + reasoning 충분
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RERANKER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500,
        )

        # ─────────────────────────────────────────────────────────────
        # 응답 파싱 & 검증
        # ─────────────────────────────────────────────────────────────
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("LLM이 빈 응답을 반환했습니다")

        try:
            parsed_json = json.loads(raw_content)
            result = RerankerOutput(**parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {raw_content}")
            raise ValueError(f"LLM 응답이 유효한 JSON이 아닙니다: {e}") from e

        # ─────────────────────────────────────────────────────────────
        # video_id 검증 (환각 방지)
        # ─────────────────────────────────────────────────────────────
        # LLM이 존재하지 않는 video_id를 지어낼 수 있음
        # → 후보 리스트에 있는 것만 허용
        
        candidate_ids = {c["video_id"] for c in candidates}
        for rec in result.recommendations:
            if rec.video_id not in candidate_ids:
                logger.error(f"❌ LLM 환각 감지: video_id={rec.video_id}")
                raise ValueError(
                    f"LLM이 존재하지 않는 video_id를 반환: {rec.video_id}"
                )

        tokens_used = response.usage.total_tokens

        logger.info(
            f"✨ Re-rank 완료: top_6={len(result.recommendations)}, "
            f"tokens={tokens_used}, "
            f"cost=${(tokens_used / 1_000_000) * 0.3:.6f}"
        )

        return result, tokens_used

    # =========================================================================
    # 헬퍼 메서드: 컨텍스트 요약
    # =========================================================================
    # 
    # 목적:
    # - LLM에게 사용자 정보를 명확하게 전달
    # - 토큰 절약 (전체 데이터 X, 핵심만)
    # - 프롬프트 가독성 향상

    def _summarize_weaknesses(self, weaknesses: list[dict]) -> str:
        """약점 표현을 문자열로 요약"""
        if not weaknesses:
            return "None"
        
        # 최대 5개까지만 (토큰 절약)
        items = [
            f'"{w.get("weak_expression", "")}" (should be: "{w.get("recommended_expression", "")}")'
            for w in weaknesses[:5]
        ]
        return "; ".join(items)

    def _summarize_weak_words(self, weak_words: list[dict]) -> str:
        """취약 단어를 문자열로 요약"""
        if not weak_words:
            return "None"
        
        # 정답률 낮은 순으로 정렬 (이미 정렬돼있다고 가정)
        words = [w.get("word", "") for w in weak_words[:10]]
        return ", ".join(words)

    def _summarize_collected_words(self, collected_words: list[dict]) -> str:
        """수집 단어를 문자열로 요약"""
        if not collected_words:
            return "None"
        
        words = [w.get("word", "") for w in collected_words[:15]]
        return ", ".join(words)

    def _format_candidates(self, candidates: list[dict]) -> str:
        """
        후보 영상 리스트를 LLM이 읽기 쉬운 형식으로 포맷팅 (Phase 6.5 압축)
        
        압축 형식 (한 줄):
        [1] id=abc123 | Title (80자) | @Channel | q:matched_query
        
        효과:
        - 프롬프트 크기 60% 감소
        - LLM 처리 속도 향상
        - 비용 절감
        """
        lines = []
        for i, c in enumerate(candidates, 1):
            # title 80자로 제한 (긴 제목 방지)
            title = c['title'][:80]
            # matched_query 30자로 제한
            matched = c.get('matched_query', '')[:30]
            
            lines.append(
                f"[{i}] id={c['video_id']} | {title} | @{c['channel_name']} | q:{matched}"
            )
        return "\n".join(lines)

# =============================================================================
# 싱글톤
# =============================================================================

_reranker: RerankerService | None = None


def get_reranker() -> RerankerService:
    """RerankerService 싱글톤 반환"""
    global _reranker
    if _reranker is None:
        _reranker = RerankerService()
    return _reranker