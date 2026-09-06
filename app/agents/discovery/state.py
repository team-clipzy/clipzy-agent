"""
Content Discovery Agent - State 정의

역할:
- Agent 워크플로우 전체에서 공유되는 상태
- 각 노드가 이 상태를 읽고 업데이트
- 최종적으로 상태에서 결과 추출

LangGraph의 State는 TypedDict로 정의:
- 타입 안전성
- IDE 자동완성
- 명확한 스키마
"""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """
    Content Discovery Agent의 상태
    
    각 노드는 이 상태를 받아 필요한 필드를 업데이트합니다.
    
    Flow:
    1. profile_loader → profile_text, metadata 추가
    2. query_generator → queries, query_reasoning 추가
    3. candidate_finder → candidates, cache_stats 추가
    4. reranker → recommendations, strategy 추가
    5. quality_check → quality_score, should_retry 결정
    """
    
    # ─────────────────────────────────────────────────────────
    # 입력 (초기값)
    # ─────────────────────────────────────────────────────────
    user_id: int
    max_videos_per_query: int
    force_refresh: bool
    
    # ─────────────────────────────────────────────────────────
    # profile_loader 노드 결과
    # ─────────────────────────────────────────────────────────
    profile_text: str
    metadata: dict[str, Any]
    
    # ─────────────────────────────────────────────────────────
    # query_generator 노드 결과
    # ─────────────────────────────────────────────────────────
    queries: list[str]
    query_reasoning: str
    tokens_used_query: int
    
    # ─────────────────────────────────────────────────────────
    # candidate_finder 노드 결과
    # ─────────────────────────────────────────────────────────
    candidates: list[dict[str, Any]]
    cache_hits: int
    cache_misses: int
    
    # ─────────────────────────────────────────────────────────
    # reranker 노드 결과
    # ─────────────────────────────────────────────────────────
    recommendations: list[dict[str, Any]]
    overall_strategy: str
    tokens_used_rerank: int
    
    # ─────────────────────────────────────────────────────────
    # quality_check 노드 결과
    # ─────────────────────────────────────────────────────────
    quality_score: float          # 0.0 ~ 1.0
    quality_feedback: str         # 품질 평가 이유
    should_retry: bool            # 재시도 여부
    
    # ─────────────────────────────────────────────────────────
    # 메타 정보 (전체 흐름 추적)
    # ─────────────────────────────────────────────────────────
    retry_count: int              # 재시도 횟수
    errors: list[str]             # 발생한 에러 목록
    node_history: list[str]       # 실행된 노드 목록


def create_initial_state(
    user_id: int,
    max_videos_per_query: int = 10,
    force_refresh: bool = False,
) -> AgentState:
    """
    초기 상태 생성
    
    Agent 실행 시작 시 호출되는 팩토리 함수
    """
    return AgentState(
        # 입력
        user_id=user_id,
        max_videos_per_query=max_videos_per_query,
        force_refresh=force_refresh,
        
        # 나머지는 빈 값으로 초기화
        profile_text="",
        metadata={},
        queries=[],
        query_reasoning="",
        tokens_used_query=0,
        candidates=[],
        cache_hits=0,
        cache_misses=0,
        recommendations=[],
        overall_strategy="",
        tokens_used_rerank=0,
        quality_score=0.0,
        quality_feedback="",
        should_retry=False,
        retry_count=0,
        errors=[],
        node_history=[],
    )