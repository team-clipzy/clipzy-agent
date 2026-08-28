"""
로거 설정
Loguru를 사용해 예쁘고 강력한 로그를 출력합니다.
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logger() -> None:
    """로거 초기화"""

    # 기본 핸들러 제거
    logger.remove()

    # 콘솔 출력 (컬러 포함)
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.is_development,  # 개발 환경에서만 상세 트레이스백
    )

    # 파일 출력 (프로덕션 환경만)
    if settings.is_production:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            rotation="00:00",  # 매일 자정 로테이션
            retention="30 days",
            compression="zip",
            level="INFO",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
        )

    logger.info(f"✅ Logger initialized (env: {settings.app_env})")


# 외부에서 import 하기 쉽게
__all__ = ["logger", "setup_logger"]