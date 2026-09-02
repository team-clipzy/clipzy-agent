"""
사용자 학습 프로필 관련 Pydantic 스키마
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================
# 원본 데이터 스키마 (Spring에서 받아올 형태)
# =============================================

class CollectedWord(BaseModel):
    """수집한 단어"""

    word: str
    translation: str
    collected_at: datetime | None = None


class UserWeakness(BaseModel):
    """채팅 약점 표현"""

    weak_expression: str
    recommended_expression: str
    review_count: int = 0


class QuizPerformance(BaseModel):
    """퀴즈 성과 (취약 단어 파악용)"""

    word: str
    total_attempts: int
    correct_count: int

    @property
    def accuracy(self) -> float:
        """정답률"""
        if self.total_attempts == 0:
            return 0.0
        return self.correct_count / self.total_attempts


class VideoProgress(BaseModel):
    """영상 학습 이력"""

    video_id: str
    video_title: str | None = None
    learning_goal: str | None = None  # TRAVEL, DAILY, BUSINESS
    completion_count: int = 0
    total_watch_time: int = 0  # 초 단위


# =============================================
# 프로필 생성 요청/응답
# =============================================

class BuildProfileRequest(BaseModel):
    """
    사용자 프로필 임베딩 생성 요청
    Spring 서버에서 사용자 데이터를 모아 보내줌
    """

    user_id: int = Field(..., description="사용자 ID")

    # 기본 정보
    learning_goal: str = Field(
        ...,
        description="학습 목표",
        examples=["TRAVEL", "DAILY", "BUSINESS"],
    )
    absolute_level: str = Field(
        ...,
        description="영어 수준",
        examples=["BEGINNER", "INTERMEDIATE", "ADVANCED"],
    )

    # 학습 데이터
    recent_collected_words: list[CollectedWord] = Field(
        default_factory=list,
        description="최근 수집 단어 (최대 20개)",
    )
    weaknesses: list[UserWeakness] = Field(
        default_factory=list,
        description="채팅 약점 표현 (최대 10개)",
    )
    weak_words: list[QuizPerformance] = Field(
        default_factory=list,
        description="정답률 낮은 단어 (정답률 50% 미만)",
    )
    completed_videos: list[VideoProgress] = Field(
        default_factory=list,
        description="완주한 영상 이력",
    )


class ProfileResponse(BaseModel):
    """프로필 조회 응답"""

    user_id: int
    profile_text: str = Field(description="LLM/임베딩용 프로필 텍스트")
    embedding_preview: list[float] = Field(description="벡터 앞 5개 (미리보기)")
    dimension: int
    qdrant_point_id: str
    created_at: str
    metadata: dict[str, Any]


class GetProfileResponse(BaseModel):
    """저장된 프로필 조회 응답"""

    user_id: int
    exists: bool
    profile: ProfileResponse | None = None