"""
애플리케이션 설정 관리
.env 파일을 읽어서 타입 안전한 설정 객체로 제공합니다.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 전역 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # .env에 정의되지 않은 변수는 무시
    )

    # =============================================
    # Application
    # =============================================
    app_name: str = Field(default="clipzy-agent", description="애플리케이션 이름")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="실행 환경"
    )
    app_host: str = Field(default="0.0.0.0", description="서버 호스트")
    app_port: int = Field(default=8000, description="서버 포트")
    log_level: str = Field(default="INFO", description="로그 레벨")

    # =============================================
    # OpenAI
    # =============================================
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_model_chat: str = Field(
        default="gpt-4o-mini", description="LLM 모델"
    )
    openai_model_embedding: str = Field(
        default="text-embedding-3-small", description="임베딩 모델"
    )

    # =============================================
    # YouTube Data API
    # =============================================
    youtube_api_key: str = Field(default="", description="YouTube Data API Key")

    # =============================================
    # Qdrant
    # =============================================
    qdrant_host: str = Field(default="localhost", description="Qdrant 호스트")
    qdrant_port: int = Field(default=6333, description="Qdrant 포트")
    qdrant_collection_video: str = Field(
        default="clipzy_videos", description="영상 컬렉션 이름"
    )
    qdrant_collection_user: str = Field(
        default="clipzy_users", description="사용자 컬렉션 이름"
    )

    # =============================================
    # MySQL
    # =============================================
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=3306)
    db_name: str = Field(default="clipzy")
    db_user: str = Field(default="root")
    db_password: str = Field(default="")

    @property
    def db_url(self) -> str:
        """SQLAlchemy 연결 URL"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    # =============================================
    # Redis
    # =============================================
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    @property
    def redis_url(self) -> str:
        """Redis 연결 URL"""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # =============================================
    # JWT
    # =============================================
    jwt_secret: str = Field(
        default="", description="JWT Secret (Spring과 동일해야 함)"
    )
    jwt_algorithm: str = Field(default="HS256")

    # =============================================
    # Spring Server
    # =============================================
    spring_server_url: str = Field(default="http://localhost:8080")
    internal_api_key: str = Field(default="")

    # =============================================
    # Helper Properties
    # =============================================
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환 (캐싱)"""
    return Settings()


# 편의를 위한 전역 인스턴스
settings = get_settings()