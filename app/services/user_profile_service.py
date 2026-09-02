"""
사용자 학습 프로필 서비스
사용자 데이터를 종합해 임베딩 벡터로 변환 & Qdrant에 저장합니다.
"""

from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.schemas.user_profile import BuildProfileRequest
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import get_qdrant_service


class UserProfileService:
    """사용자 프로필 임베딩 관리"""

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.qdrant = get_qdrant_service()
        self.collection = settings.qdrant_collection_user
        logger.info("👤 UserProfileService 초기화 완료")

    def build_profile_text(self, request: BuildProfileRequest) -> str:
        """
        사용자 데이터를 임베딩용 텍스트로 변환

        임베딩 품질을 위해 자연스러운 문장으로 구성
        """
        parts = []

        # 1. 학습 목표 & 난이도
        goal_map = {
            "TRAVEL": "traveling and tourism",
            "DAILY": "daily conversation",
            "BUSINESS": "business English",
        }
        level_map = {
            "BEGINNER": "beginner",
            "INTERMEDIATE": "intermediate",
            "ADVANCED": "advanced",
        }

        goal_text = goal_map.get(request.learning_goal, request.learning_goal)
        level_text = level_map.get(request.absolute_level, request.absolute_level)

        parts.append(
            f"This user is a {level_text} English learner "
            f"focused on {goal_text}."
        )

        # 2. 최근 수집 단어 (관심 어휘)
        if request.recent_collected_words:
            words = [cw.word for cw in request.recent_collected_words[:20]]
            parts.append(
                f"Recently collected vocabulary: {', '.join(words)}."
            )

        # 3. 채팅 약점 표현 (진짜 취약점)
        if request.weaknesses:
            expressions = [w.weak_expression for w in request.weaknesses[:10]]
            parts.append(
                f"Struggles with these expressions in conversation: "
                f"{', '.join(expressions)}."
            )

        # 4. 정답률 낮은 단어 (퀴즈 취약)
        if request.weak_words:
            weak = [wp.word for wp in request.weak_words[:10]]
            parts.append(
                f"Has difficulty remembering: {', '.join(weak)}."
            )

        # 5. 완주한 영상 주제 (선호 콘텐츠)
        if request.completed_videos:
            topics = list(
                {v.learning_goal for v in request.completed_videos if v.learning_goal}
            )
            if topics:
                topics_text = [goal_map.get(t, t) for t in topics]
                parts.append(
                    f"Has completed videos about: {', '.join(topics_text)}."
                )

            # 학습 스타일 판단
            total_completions = sum(
                v.completion_count for v in request.completed_videos
            )
            if total_completions >= 10:
                parts.append("This user is a dedicated learner who completes videos multiple times.")
            elif total_completions >= 3:
                parts.append("This user shows consistent learning habits.")
            else:
                parts.append("This user is a casual learner exploring content.")

        profile_text = " ".join(parts)
        logger.debug(f"프로필 텍스트 생성 완료: length={len(profile_text)}")
        return profile_text

    async def build_and_save_profile(
        self,
        request: BuildProfileRequest,
    ) -> dict[str, Any]:
        """
        프로필 텍스트 생성 → 임베딩 → Qdrant 저장

        Returns:
            생성된 프로필 정보
        """
        # 1. 프로필 텍스트 생성
        profile_text = self.build_profile_text(request)

        # 2. 임베딩
        embedding = await self.embedding_service.embed(profile_text)

        # 3. Qdrant 저장 (user_id를 point_id로 사용)
        payload = {
            "user_id": request.user_id,
            "profile_text": profile_text,
            "learning_goal": request.learning_goal,
            "absolute_level": request.absolute_level,
            "num_collected_words": len(request.recent_collected_words),
            "num_weaknesses": len(request.weaknesses),
            "num_weak_words": len(request.weak_words),
            "num_completed_videos": len(request.completed_videos),
            "updated_at": datetime.now().isoformat(),
        }

        point_id = self.qdrant.upsert_point(
            collection_name=self.collection,
            embedding=embedding,
            payload=payload,
            point_id=request.user_id,  # user_id를 point_id로 사용
        )

        logger.info(
            f"✅ 프로필 저장 완료: user_id={request.user_id}, "
            f"text_length={len(profile_text)}, "
            f"vector_dim={len(embedding)}"
        )

        return {
            "user_id": request.user_id,
            "profile_text": profile_text,
            "embedding_preview": embedding[:5],
            "dimension": len(embedding),
            "qdrant_point_id": point_id,
            "created_at": datetime.now().isoformat(),
            "metadata": payload,
        }

    def get_profile(self, user_id: int) -> dict[str, Any] | None:
        """
        저장된 사용자 프로필 조회

        Args:
            user_id: 사용자 ID

        Returns:
            프로필 정보 or None (없음)
        """
        try:
            # Qdrant에서 특정 point_id로 조회
            points = self.qdrant.client.retrieve(
                collection_name=self.collection,
                ids=[user_id],
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                logger.info(f"프로필 없음: user_id={user_id}")
                return None

            point = points[0]
            return {
                "user_id": user_id,
                "profile_text": point.payload.get("profile_text", ""),
                "embedding_preview": point.vector[:5] if point.vector else [],
                "dimension": len(point.vector) if point.vector else 0,
                "qdrant_point_id": str(point.id),
                "created_at": point.payload.get("updated_at", ""),
                "metadata": point.payload,
            }

        except Exception as e:
            logger.error(f"프로필 조회 실패: user_id={user_id}, error={e}")
            return None

    def delete_profile(self, user_id: int) -> bool:
        """
        사용자 프로필 삭제
        (GDPR 데이터 삭제 요청 대응)

        Args:
            user_id: 사용자 ID

        Returns:
            성공 여부
        """
        try:
            self.qdrant.delete_point(
                collection_name=self.collection,
                point_id=user_id,
            )
            logger.info(f"🗑 프로필 삭제 완료: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"프로필 삭제 실패: user_id={user_id}, error={e}")
            return False


# 싱글톤 인스턴스
_user_profile_service: UserProfileService | None = None


def get_user_profile_service() -> UserProfileService:
    """UserProfileService 싱글톤 반환"""
    global _user_profile_service
    if _user_profile_service is None:
        _user_profile_service = UserProfileService()
    return _user_profile_service