"""
Content Discovery Agent - State 정의 (옵션 A: Spring 통합)

역할:
- Agent 워크플로우 전체에서 공유되는 상태
- 각 노드가 이 상태를 읽고 업데이트
- 최종적으로 상태에서 결과 추출

LangGraph의 State는 TypedDict로 정의:
- 타입 안전성
- IDE 자동완성
- 명확한 스키마

Phase 6 → 옵션 A 확장:
- Spring 통합 필드 추가
- 시청 이력 제외 (excluded_video_ids)
- 개인화 데이터 (weaknesses, weak_words, collected_words)
"""

from typing import Any, TypedDict


class AgentState(TypedDict):
    """
    Content Discovery Agent의 상태
    
    각 노드는 이 상태를 받아 필요한 필드를 업데이트합니다.
    
    Flow:
    1. profile_loader → profile_text, metadata 추가
    2. query_generator → queries, query_reasoning 추가
    3. candidate_finder → candidates, cache_stats 추가 (시청이력 제외)
    4. reranker → recommendations, strategy 추가 (개인화 데이터 반영)
    5. quality_check → quality_score, should_retry 결정
    """
    
    # ─────────────────────────────────────────────────────────
    # 입력 (초기값)
    # ─────────────────────────────────────────────────────────
    user_id: int
    max_videos_per_query: int
    force_refresh: bool
    
    # ─────────────────────────────────────────────────────────
    # ⭐ Spring 통합용 필드 (옵션 A)
    # ─────────────────────────────────────────────────────────
    # 시청 이력 (candidate_finder에서 제외 처리)
    excluded_video_ids: list[str]
    
    # 개인화 데이터 (reranker에서 활용)
    external_weaknesses: list[dict]        # 약점 표현
    external_weak_words: list[dict]        # 취약 단어
    external_collected_words: list[dict]   # 수집 단어
    
    # 외부 데이터 사용 여부
    # True: Spring에서 받은 데이터 사용 (recommend-full)
    # False: Qdrant 프로필만 사용 (recommend-v2)
    use_external_data: bool
    
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
    excluded_count: int  # ⭐ NEW: 시청 이력으로 제외된 영상 수
    
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
    # ⭐ Spring 통합용 파라미터
    excluded_video_ids: list[str] | None = None,
    external_weaknesses: list[dict] | None = None,
    external_weak_words: list[dict] | None = None,
    external_collected_words: list[dict] | None = None,
    use_external_data: bool = False,
) -> AgentState:
    """
    초기 상태 생성 (Spring 통합 지원)
    
    Agent 실행 시작 시 호출되는 팩토리 함수
    
    Args:
        user_id: 사용자 ID
        max_videos_per_query: 검색어당 최대 영상 수 (기본 10)
        force_refresh: 캐시 무시 여부
        
        # Spring 통합용 (옵션 A)
        excluded_video_ids: 제외할 video_id 목록 (시청 이력)
        external_weaknesses: Spring이 전달한 약점 표현
        external_weak_words: Spring이 전달한 취약 단어
        external_collected_words: Spring이 전달한 수집 단어
        use_external_data: True면 Spring 데이터 사용
    
    Returns:
        초기화된 AgentState
    
    Examples:
        # 기존 recommend-v2 방식 (Qdrant만)
        state = create_initial_state(user_id=1)
        
        # 새로운 recommend-full 방식 (Spring 통합)
        state = create_initial_state(
            user_id=1,
            excluded_video_ids=["watched1", "watched2"],
            external_weaknesses=[{"weak_expression": "check-in"}],
            external_weak_words=[{"word": "itinerary"}],
            external_collected_words=[{"word": "airport"}],
            use_external_data=True,
        )
    """
    return AgentState(
        # 입력
        user_id=user_id,
        max_videos_per_query=max_videos_per_query,
        force_refresh=force_refresh,
        
        # Spring 통합용
        excluded_video_ids=excluded_video_ids or [],
        external_weaknesses=external_weaknesses or [],
        external_weak_words=external_weak_words or [],
        external_collected_words=external_collected_words or [],
        use_external_data=use_external_data,
        
        # profile_loader
        profile_text="",
        metadata={},
        
        # query_generator
        queries=[],
        query_reasoning="",
        tokens_used_query=0,
        
        # candidate_finder
        candidates=[],
        cache_hits=0,
        cache_misses=0,
        excluded_count=0,  # ⭐ NEW
        
        # reranker
        recommendations=[],
        overall_strategy="",
        tokens_used_rerank=0,
        
        # quality_check
        quality_score=0.0,
        quality_feedback="",
        should_retry=False,
        
        # 메타 정보
        retry_count=0,
        errors=[],
        node_history=[],
    )