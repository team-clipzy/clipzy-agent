"""
Spring 서버 통합용 스키마 (camelCase 직접 지원)
"""

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# 요청 스키마 (camelCase 직접 사용)
# =============================================================================

class WeaknessDto(BaseModel):
    """약점 표현 (Spring에서 전달)"""
    weakExpression: str = ""
    recommendedExpression: str = ""
    reviewCount: int = 0
    
    model_config = ConfigDict(extra='allow')


class WeakWordDto(BaseModel):
    """취약 단어 (Spring에서 전달)"""
    word: str
    meaning: str = ""
    correctRate: float = 0.0
    
    model_config = ConfigDict(extra='allow')


class CollectedWordDto(BaseModel):
    """수집 단어 (Spring에서 전달)"""
    word: str
    meaning: str = ""
    
    model_config = ConfigDict(extra='allow')


class FullRecommendRequest(BaseModel):
    """
    Spring이 FastAPI에 보내는 완전한 추천 요청
    
    Spring의 camelCase JSON을 그대로 받음
    """
    userId: int = Field(description="사용자 ID")
    learningGoal: str = Field(description="학습 목표")
    absoluteLevel: str = Field(description="영어 수준")
    
    excludedVideoIds: list[str] = Field(default_factory=list)
    weaknesses: list[WeaknessDto] = Field(default_factory=list)
    weakWords: list[WeakWordDto] = Field(default_factory=list)
    collectedWords: list[CollectedWordDto] = Field(default_factory=list)
    
    model_config = ConfigDict(
        extra='allow',
        json_schema_extra={
            "example": {
                "userId": 1,
                "learningGoal": "TRAVEL",
                "absoluteLevel": "BEGINNER",
                "excludedVideoIds": ["video1", "video2"],
                "weaknesses": [
                    {
                        "weakExpression": "check-in",
                        "recommendedExpression": "check in, please",
                        "reviewCount": 3
                    }
                ],
                "weakWords": [
                    {"word": "itinerary", "correctRate": 0.4}
                ],
                "collectedWords": [
                    {"word": "airport"},
                    {"word": "hotel"}
                ]
            }
        }
    )
    
    # ⭐ Python 코드에서 편하게 사용하기 위한 프로퍼티
    @property
    def user_id(self) -> int:
        return self.userId
    
    @property
    def learning_goal(self) -> str:
        return self.learningGoal
    
    @property
    def absolute_level(self) -> str:
        return self.absoluteLevel
    
    @property
    def excluded_video_ids(self) -> list[str]:
        return self.excludedVideoIds
    
    @property
    def weak_words(self) -> list[WeakWordDto]:
        return self.weakWords
    
    @property
    def collected_words(self) -> list[CollectedWordDto]:
        return self.collectedWords


# =============================================================================
# 응답 스키마 (camelCase로 반환)
# =============================================================================

class FullRecommendedVideo(BaseModel):
    """AI가 추천한 영상 (Spring에 반환)"""
    videoId: str
    rank: int
    reason: str
    relevanceScore: float
    
    title: str
    channelId: str
    channelName: str
    thumbnailUrl: str
    description: str = ""
    publishedAt: str = ""


class FullRecommendResponse(BaseModel):
    """Spring에 반환하는 최종 응답"""
    recommendations: list[FullRecommendedVideo]
    strategy: str
    
    totalCandidates: int
    excludedCount: int
    processingTimeMs: int
    tokensUsed: int
    qualityScore: float
    retryCount: int