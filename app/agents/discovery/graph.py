"""
Content Discovery Agent - LangGraph 워크플로우

역할:
- 모든 노드를 하나의 워크플로우로 조립
- 조건부 흐름 정의 (재시도)
- Compile 후 재사용 가능한 Agent

사용법:
    agent = get_discovery_agent()
    result = await agent.ainvoke(initial_state)
"""

from langgraph.graph import END, StateGraph

from app.agents.discovery.nodes import (
    candidate_finder_node,
    profile_loader_node,
    quality_check_node,
    query_generator_node,
    reranker_node,
    should_retry_or_end,
)
from app.agents.discovery.state import AgentState
from app.core.logger import logger


def build_discovery_agent():
    """
    Content Discovery Agent 워크플로우 구축
    
    Flow:
        START
          ↓
        profile_loader
          ↓
        query_generator ←─────┐
          ↓                   │
        candidate_finder      │ 재시도
          ↓                   │
        reranker              │
          ↓                   │
        quality_check ────────┤
          ↓                   │
         END           (품질 낮으면)
    
    Returns:
        컴파일된 Agent (재사용 가능)
    """
    logger.info("🏗 Discovery Agent 워크플로우 구축 시작")
    
    # StateGraph 생성 (AgentState 타입 사용)
    workflow = StateGraph(AgentState)
    
    # ─────────────────────────────────────────────────────────
    # 노드 등록
    # ─────────────────────────────────────────────────────────
    workflow.add_node("profile_loader", profile_loader_node)
    workflow.add_node("query_generator", query_generator_node)
    workflow.add_node("candidate_finder", candidate_finder_node)
    workflow.add_node("reranker", reranker_node)
    workflow.add_node("quality_check", quality_check_node)
    
# ─────────────────────────────────────────────────────────
    # 진입점 설정
    # ─────────────────────────────────────────────────────────
    workflow.set_entry_point("profile_loader")
    
    # ─────────────────────────────────────────────────────────
    # 엣지 연결 (노드 간 흐름)
    # ─────────────────────────────────────────────────────────
    # 순차 흐름
    workflow.add_edge("profile_loader", "query_generator")
    workflow.add_edge("query_generator", "candidate_finder")
    workflow.add_edge("candidate_finder", "reranker")
    workflow.add_edge("reranker", "quality_check")
    
    # ─────────────────────────────────────────────────────────
    # 조건부 엣지 (품질 검증 후 분기)
    # ─────────────────────────────────────────────────────────
    # quality_check → {retry, end}
    workflow.add_conditional_edges(
        "quality_check",
        should_retry_or_end,  # 라우팅 함수
        {
            "retry": "query_generator",  # 재시도 시 검색어부터 다시
            "end": END,                   # 통과 시 종료
        }
    )
    
    # ─────────────────────────────────────────────────────────
    # 컴파일 (실행 가능한 Agent로 변환)
    # ─────────────────────────────────────────────────────────
    agent = workflow.compile()
    
    logger.info("✅ Discovery Agent 워크플로우 구축 완료")
    return agent


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================
# Agent는 한 번 컴파일하면 재사용 가능
# 매번 컴파일하면 성능 낭비

_discovery_agent = None


def get_discovery_agent():
    """Discovery Agent 싱글톤 반환"""
    global _discovery_agent
    if _discovery_agent is None:
        _discovery_agent = build_discovery_agent()
    return _discovery_agent