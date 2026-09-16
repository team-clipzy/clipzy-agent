"""
Content Discovery Agent - 노드 함수들 (옵션 A 확장)

각 노드는 State를 받아서 State를 반환하는 순수 함수

노드 종류:
1. profile_loader_node: 프로필 로드 (Qdrant or Spring 데이터)
2. query_generator_node: 검색어 생성
3. candidate_finder_node: YouTube 검색 + 시청 이력 제외
4. reranker_node: Top 6 선정 + 개인화 반영
5. quality_check_node: 품질 검증 (Self-Reflection)

라우팅 함수:
- should_retry: 재시도 여부 판단
"""

from typing import Literal

from app.agents.discovery.candidate_finder import get_candidate_finder
from app.agents.discovery.query_generator import get_query_generator
from app.agents.discovery.reranker import get_reranker
from app.agents.discovery.state import AgentState
from app.core.logger import logger
from app.services.user_profile_service import get_user_profile_service


# =============================================================================
# Node 1: Profile Loader (Spring 데이터 지원)
# =============================================================================

async def profile_loader_node(state: AgentState) -> AgentState:
    """
    사용자 프로필 로드 노드
    
    2가지 모드:
    1. use_external_data=False (기본): Qdrant에서 프로필 조회
    2. use_external_data=True (Spring): Spring 데이터로 프로필 생성
    
    Input: user_id, use_external_data, external_* 
    Output: profile_text, metadata
    """
    logger.info(f"🎯 [Node] profile_loader 실행: user_id={state['user_id']}, external={state['use_external_data']}")
    state["node_history"].append("profile_loader")
    
    try:
        # ─────────────────────────────────────────────────────────
        # 모드 1: Spring 데이터로 프로필 구축 (recommend-full)
        # ─────────────────────────────────────────────────────────
        if state["use_external_data"]:
            # Spring이 전달한 데이터로 프로필 텍스트 생성
            profile_text = _build_profile_from_spring(state)
            
            # 메타데이터 구성 (Qdrant 저장 형식과 호환)
            metadata = {
                "learning_goal": state.get("metadata", {}).get("learning_goal", "TRAVEL"),
                "absolute_level": state.get("metadata", {}).get("absolute_level", "BEGINNER"),
                "num_weaknesses": len(state["external_weaknesses"]),
                "num_collected_words": len(state["external_collected_words"]),
                "num_completed_videos": 0,  # 시청 이력 개수는 excluded_video_ids로
                "num_excluded_videos": len(state["excluded_video_ids"]),
            }
            
            state["profile_text"] = profile_text
            state["metadata"] = metadata
            
            logger.info(
                f"✅ profile_loader 완료 (Spring 데이터): "
                f"weaknesses={metadata['num_weaknesses']}, "
                f"collected={metadata['num_collected_words']}, "
                f"excluded={metadata['num_excluded_videos']}"
            )
            return state
        
        # ─────────────────────────────────────────────────────────
        # 모드 2: Qdrant에서 프로필 조회 (기존 recommend-v2)
        # ─────────────────────────────────────────────────────────
        profile_service = get_user_profile_service()
        profile = profile_service.get_profile(state["user_id"])
        
        if profile is None:
            error = f"프로필 없음: user_id={state['user_id']}"
            state["errors"].append(error)
            logger.error(f"❌ {error}")
            raise ValueError(error)
        
        state["profile_text"] = profile["profile_text"]
        state["metadata"] = profile["metadata"]
        
        logger.info(f"✅ profile_loader 완료 (Qdrant)")
        return state
        
    except Exception as e:
        state["errors"].append(f"profile_loader: {str(e)}")
        raise


def _build_profile_from_spring(state: AgentState) -> str:
    """Spring 데이터로 자연어 프로필 텍스트 생성"""
    parts = []
    
    learning_goal = state.get("metadata", {}).get("learning_goal", "TRAVEL")
    absolute_level = state.get("metadata", {}).get("absolute_level", "BEGINNER")
    
    parts.append(f"This user is a {absolute_level} level English learner.")
    
    # ⭐ NONE 처리
    if learning_goal == "NONE":
        parts.append("They have no specific learning goal - they want general English content that matches their level.")
    else:
        parts.append(f"Their learning goal is: {learning_goal}.")
    
    # 약점 표현
    weaknesses = state["external_weaknesses"]
    if weaknesses:
        weakness_texts = []
        for w in weaknesses[:5]:  # 최대 5개
            weak = w.get("weak_expression", "")
            recommended = w.get("recommended_expression", "")
            if weak and recommended:
                weakness_texts.append(f'"{weak}" (should be: "{recommended}")')
            elif weak:
                weakness_texts.append(f'"{weak}"')
        
        if weakness_texts:
            parts.append(
                f"They struggle with these expressions: {'; '.join(weakness_texts)}."
            )
    
    # 취약 단어
    weak_words = state["external_weak_words"]
    if weak_words:
        words = [w.get("word", "") for w in weak_words[:10] if w.get("word")]
        if words:
            parts.append(f"They have difficulty with these words: {', '.join(words)}.")
    
    # 수집 단어
    collected = state["external_collected_words"]
    if collected:
        words = [w.get("word", "") for w in collected[:15] if w.get("word")]
        if words:
            parts.append(f"They have collected these words for learning: {', '.join(words)}.")
    
    # 시청 이력 정보
    excluded_count = len(state["excluded_video_ids"])
    if excluded_count > 0:
        parts.append(f"They have already watched {excluded_count} videos.")
    
    return " ".join(parts)


# =============================================================================
# Node 2: Query Generator (변경 없음, 기존 유지)
# =============================================================================

async def query_generator_node(state: AgentState) -> AgentState:
    """
    LLM 검색어 생성 노드
    
    Input: profile_text, metadata
    Output: queries, query_reasoning, tokens_used_query
    """
    logger.info(f"🧠 [Node] query_generator 실행")
    state["node_history"].append("query_generator")
    
    try:
        generator = get_query_generator()
        result, tokens = await generator.generate(
            profile_text=state["profile_text"],
            learning_goal=state["metadata"].get("learning_goal", "TRAVEL"),
            absolute_level=state["metadata"].get("absolute_level", "BEGINNER"),
            num_collected_words=state["metadata"].get("num_collected_words", 0),
            num_weaknesses=state["metadata"].get("num_weaknesses", 0),
            num_completed_videos=state["metadata"].get("num_completed_videos", 0),
        )
        
        state["queries"] = result.queries
        state["query_reasoning"] = result.reasoning
        state["tokens_used_query"] = tokens
        
        logger.info(f"✅ query_generator 완료: {len(result.queries)}개 생성")
        return state
        
    except Exception as e:
        state["errors"].append(f"query_generator: {str(e)}")
        raise


# =============================================================================
# Node 3: Candidate Finder (시청 이력 제외)
# =============================================================================

async def candidate_finder_node(state: AgentState) -> AgentState:
    """
    YouTube 후보 영상 검색 노드
    
    옵션 A 확장:
    - excluded_video_ids로 시청 이력 자동 제외
    - 제외 후 6개 미만이면 추가 검색 (max_results 늘려서 재시도)
    
    Input: queries, excluded_video_ids
    Output: candidates (시청이력 제외됨), cache_hits, cache_misses, excluded_count
    """
    logger.info(f"🔎 [Node] candidate_finder 실행")
    state["node_history"].append("candidate_finder")
    
    try:
        finder = get_candidate_finder()
        result = await finder.find_candidates(
            queries=state["queries"],
            max_results_per_query=state["max_videos_per_query"],
            force_refresh=state["force_refresh"],
        )
        
        all_candidates = result["videos"]
        excluded_ids_set = set(state["excluded_video_ids"])
        
        # 시청 이력 제외
        if excluded_ids_set:
            before_count = len(all_candidates)
            filtered_candidates = [
                v for v in all_candidates 
                if v["video_id"] not in excluded_ids_set
            ]
            excluded_count = before_count - len(filtered_candidates)
            
            logger.info(
                f"🚫 시청 이력 제외: {before_count}개 → {len(filtered_candidates)}개 "
                f"(제외={excluded_count}개)"
            )
        else:
            filtered_candidates = all_candidates
            excluded_count = 0
        
        # 후보가 6개 미만이면 경고 (재시도는 quality_check에서)
        if len(filtered_candidates) < 6:
            warning = (
                f"⚠️ 시청 이력 제외 후 후보 부족: {len(filtered_candidates)}개 "
                f"(최소 6개 필요)"
            )
            logger.warning(warning)
            state["errors"].append(warning)
        
        state["candidates"] = filtered_candidates
        state["cache_hits"] = result["cache_hits"]
        state["cache_misses"] = result["cache_misses"]
        state["excluded_count"] = excluded_count
        
        logger.info(
            f"✅ candidate_finder 완료: "
            f"{len(filtered_candidates)}개 후보 "
            f"(캐시 히트={result['cache_hits']}, 제외={excluded_count})"
        )
        return state
        
    except Exception as e:
        state["errors"].append(f"candidate_finder: {str(e)}")
        raise


# =============================================================================
# Node 4: Re-ranker (개인화 데이터 반영)
# =============================================================================

async def reranker_node(state: AgentState) -> AgentState:
    """
    LLM Re-ranker 노드
    
    옵션 A 확장:
    - use_external_data=True면 Spring 데이터 사용
    - use_external_data=False면 기존 방식 (빈 리스트)
    
    Input: candidates, profile_text, metadata, external_*
    Output: recommendations, overall_strategy, tokens_used_rerank
    """
    logger.info(f"🎯 [Node] reranker 실행")
    state["node_history"].append("reranker")
    
    try:
        # 후보가 6개 미만이면 에러
        if len(state["candidates"]) < 6:
            error = f"후보 부족: {len(state['candidates'])}개 (최소 6개 필요)"
            state["errors"].append(error)
            raise ValueError(error)
        
        # 개인화 데이터 준비 (모드에 따라)
        if state["use_external_data"]:
            # Spring 데이터 사용 (recommend-full)
            weaknesses = state["external_weaknesses"]
            weak_words = state["external_weak_words"]
            collected_words = state["external_collected_words"]
            logger.info(
                f"🎨 개인화 데이터 사용: "
                f"weaknesses={len(weaknesses)}, "
                f"weak_words={len(weak_words)}, "
                f"collected={len(collected_words)}"
            )
        else:
            # 기존 방식 (recommend-v2)
            weaknesses = []
            weak_words = []
            collected_words = []
        
        reranker = get_reranker()
        result, tokens = await reranker.rerank(
            profile_text=state["profile_text"],
            learning_goal=state["metadata"].get("learning_goal", "TRAVEL"),
            absolute_level=state["metadata"].get("absolute_level", "BEGINNER"),
            weaknesses=weaknesses,
            weak_words=weak_words,
            collected_words=collected_words,
            candidates=state["candidates"],
        )
        
        # 응답 조립 (video_id 매칭)
        candidates_by_id = {c["video_id"]: c for c in state["candidates"]}
        recommendations = []
        
        for ranked in result.recommendations:
            candidate = candidates_by_id.get(ranked.video_id)
            if not candidate:
                logger.warning(f"⚠️ 매칭 실패: {ranked.video_id}")
                continue
            
            recommendations.append({
                "rank": ranked.rank,
                "reason": ranked.reason,
                "video_id": candidate["video_id"],
                "title": candidate["title"],
                "description": candidate["description"][:200],
                "channel_id": candidate["channel_id"],
                "channel_name": candidate["channel_name"],
                "thumbnail_url": candidate["thumbnail_url"],
                "published_at": candidate["published_at"],
                "matched_query": candidate.get("matched_query", ""),
            })
        
        # 순위 정렬
        recommendations.sort(key=lambda x: x["rank"])
        
        state["recommendations"] = recommendations
        state["overall_strategy"] = result.overall_strategy
        state["tokens_used_rerank"] = tokens
        
        logger.info(f"✅ reranker 완료: Top {len(recommendations)} 선정")
        return state
        
    except Exception as e:
        state["errors"].append(f"reranker: {str(e)}")
        raise


# =============================================================================
# Node 5: Quality Check (Self-Reflection) - 변경 없음
# =============================================================================

async def quality_check_node(state: AgentState) -> AgentState:
    """
    추천 결과 품질 자체 검증 노드 (Self-Reflection)
    
    Input: recommendations, metadata
    Output: quality_score, quality_feedback, should_retry
    
    검증 항목:
    1. 개수 검증 (6개인가?)
    2. 다양성 검증 (같은 채널 편중?)
    3. 취약점 반영 (weaknesses 언급?)
    4. Reason 품질 (한국어, 구체성)
    """
    logger.info(f"🔍 [Node] quality_check 실행")
    state["node_history"].append("quality_check")
    
    recommendations = state["recommendations"]
    metadata = state["metadata"]
    
    # ─────────────────────────────────────────────────────────
    # 검증 1: 개수 확인 (정확히 6개?)
    # ─────────────────────────────────────────────────────────
    count_score = 1.0 if len(recommendations) == 6 else 0.0
    
    # ─────────────────────────────────────────────────────────
    # 검증 2: 채널 다양성 (같은 채널 최대 2개까지 허용)
    # ─────────────────────────────────────────────────────────
    channel_names = [r["channel_name"] for r in recommendations]
    unique_channels = len(set(channel_names))
    
    # 6개 중 최소 3개 이상 다른 채널이면 통과
    diversity_score = min(unique_channels / 3.0, 1.0)
    
    # ─────────────────────────────────────────────────────────
    # 검증 3: 취약점 반영 (num_weaknesses > 0 이면 확인)
    # ─────────────────────────────────────────────────────────
    weakness_score = 1.0  # 기본값 (약점 없으면 통과)
    
    if metadata.get("num_weaknesses", 0) > 0:
        # 최소 1개 이상의 recommendation에 취약점 관련 내용이 있어야 함
        reasons_combined = " ".join([r["reason"] for r in recommendations])
        
        # 간단한 휴리스틱: 취약 표현 키워드 체크
        weakness_keywords = ["취약", "어려워", "약점", "부족", "check-in", "itinerary"]
        has_weakness = any(kw in reasons_combined for kw in weakness_keywords)
        
        weakness_score = 1.0 if has_weakness else 0.5
    
    # ─────────────────────────────────────────────────────────
    # 검증 4: Reason 품질 (한국어, 최소 길이)
    # ─────────────────────────────────────────────────────────
    reason_scores = []
    for r in recommendations:
        reason = r["reason"]
        # 한국어 포함 여부 (한글 유니코드 범위)
        has_korean = any('\uac00' <= c <= '\ud7a3' for c in reason)
        # 최소 20자 이상
        is_long_enough = len(reason) >= 20
        
        reason_score = 1.0 if (has_korean and is_long_enough) else 0.5
        reason_scores.append(reason_score)
    
    avg_reason_score = sum(reason_scores) / len(reason_scores) if reason_scores else 0
    
    # ─────────────────────────────────────────────────────────
    # 종합 점수 계산
    # ─────────────────────────────────────────────────────────
    quality_score = (
        count_score * 0.3 +
        diversity_score * 0.3 +
        weakness_score * 0.2 +
        avg_reason_score * 0.2
    )
    
    # ─────────────────────────────────────────────────────────
    # 재시도 결정 (품질 낮고 아직 재시도 여유 있으면)
    # ─────────────────────────────────────────────────────────
    QUALITY_THRESHOLD = 0.7  # 70% 이상이면 통과
    MAX_RETRIES = 2
    
    should_retry = (
        quality_score < QUALITY_THRESHOLD and
        state["retry_count"] < MAX_RETRIES
    )
    
    # ─────────────────────────────────────────────────────────
    # 피드백 메시지 생성
    # ─────────────────────────────────────────────────────────
    feedback_parts = []
    if count_score < 1.0:
        feedback_parts.append(f"개수 부족 ({len(recommendations)}/6)")
    if diversity_score < 1.0:
        feedback_parts.append(f"채널 다양성 부족 ({unique_channels}개)")
    if weakness_score < 1.0:
        feedback_parts.append("취약점 반영 부족")
    if avg_reason_score < 1.0:
        feedback_parts.append("Reason 품질 개선 필요")
    
    quality_feedback = (
        "; ".join(feedback_parts) if feedback_parts 
        else "모든 품질 기준 통과"
    )
    
    # ─────────────────────────────────────────────────────────
    # 상태 업데이트
    # ─────────────────────────────────────────────────────────
    state["quality_score"] = round(quality_score, 2)
    state["quality_feedback"] = quality_feedback
    state["should_retry"] = should_retry
    
    if should_retry:
        state["retry_count"] += 1
        logger.warning(
            f"⚠️ 품질 미달 (score={quality_score:.2f}): {quality_feedback} "
            f"→ 재시도 {state['retry_count']}/{MAX_RETRIES}"
        )
    else:
        logger.info(
            f"✅ quality_check 통과 (score={quality_score:.2f}): {quality_feedback}"
        )
    
    return state


# =============================================================================
# 라우팅 함수: 재시도 여부 결정
# =============================================================================

def should_retry_or_end(state: AgentState) -> Literal["retry", "end"]:
    """
    quality_check 이후의 흐름 결정
    
    Returns:
        "retry": query_generator로 돌아가 재시도
        "end": 워크플로우 종료
    """
    if state["should_retry"]:
        return "retry"
    return "end"