"""
YouTube Data API 서비스
공식 YouTube Search API를 사용해 실시간 영상 검색을 담당합니다.
"""

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.logger import logger


class YouTubeService:
    """YouTube Data API v3 클라이언트"""

    def __init__(self):
        self.api_key = settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY가 설정되지 않았습니다")

        self.client = build("youtube", "v3", developerKey=self.api_key)
        logger.info("🎬 YouTubeService 초기화 완료")

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        language: str = "en",
        video_duration: str = "medium",
    ) -> list[dict[str, Any]]:
        """
        키워드로 YouTube 영상 검색 (실시간)

        Args:
            query: 검색 키워드
            max_results: 반환할 결과 수 (최대 50)
            language: 자막 언어 필터 (en, ko 등)
            video_duration: 영상 길이 (short/medium/long/any)

        Returns:
            영상 정보 리스트
        """
        try:
            request = self.client.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=max_results,
                relevanceLanguage=language,
                videoDuration=video_duration,
                videoCaption="closedCaption",  # 자막 있는 영상만
                safeSearch="moderate",
            )
            response = request.execute()

            videos = [
                {
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_name": item["snippet"]["channelTitle"],
                    "thumbnail_url": item["snippet"]["thumbnails"]["high"]["url"],
                    "published_at": item["snippet"]["publishedAt"],
                }
                for item in response.get("items", [])
            ]

            logger.info(f"🔍 YouTube 검색 완료: query='{query}', results={len(videos)}")
            return videos

        except HttpError as e:
            logger.error(f"❌ YouTube 검색 실패: {e}")
            raise

    def get_video_details(self, video_id: str) -> dict[str, Any] | None:
        """
        영상 상세 정보 조회 (실시간, 저장 X)

        Args:
            video_id: YouTube 영상 ID

        Returns:
            영상 상세 정보 or None
        """
        try:
            request = self.client.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id,
            )
            response = request.execute()

            items = response.get("items", [])
            if not items:
                logger.warning(f"⚠️ 영상 없음: video_id={video_id}")
                return None

            item = items[0]
            return {
                "video_id": video_id,
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_id": item["snippet"]["channelId"],
                "channel_name": item["snippet"]["channelTitle"],
                "thumbnail_url": item["snippet"]["thumbnails"]["high"]["url"],
                "published_at": item["snippet"]["publishedAt"],
                "duration": item["contentDetails"]["duration"],
                "view_count": int(item["statistics"].get("viewCount", 0)),
                "like_count": int(item["statistics"].get("likeCount", 0)),
                "tags": item["snippet"].get("tags", []),
                "default_language": item["snippet"].get("defaultLanguage"),
            }

        except HttpError as e:
            logger.error(f"❌ 영상 조회 실패: video_id={video_id}, error={e}")
            raise


# 싱글톤 인스턴스
_youtube_service: YouTubeService | None = None


def get_youtube_service() -> YouTubeService:
    """YouTubeService 싱글톤 반환"""
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeService()
    return _youtube_service