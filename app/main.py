"""
CLIPZY Agent Server - FastAPI 진입점
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logger import logger, setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작/종료 시 실행되는 이벤트
    """
    # 시작 시
    setup_logger()
    logger.info("🚀 CLIPZY Agent Server 시작 중...")
    logger.info(f"📌 환경: {settings.app_env}")
    logger.info(f"📌 포트: {settings.app_port}")

    # TODO: 여기서 나중에 초기화할 것들
    # - MySQL 연결 풀 생성
    # - Redis 클라이언트 초기화
    # - Qdrant 클라이언트 초기화
    # - 스케줄러 시작

    yield

    # 종료 시
    logger.info("👋 CLIPZY Agent Server 종료 중...")
    # TODO: 리소스 정리


# FastAPI 앱 생성
app = FastAPI(
    title="CLIPZY Agent API",
    description="🧠 YouTube 영어 학습 AI Agent 서버",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [settings.spring_server_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(api_router)


# 루트 엔드포인트
@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    루트 엔드포인트
    브라우저로 접속 시 표시됩니다.
    """
    return {
        "service": "CLIPZY Agent API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }