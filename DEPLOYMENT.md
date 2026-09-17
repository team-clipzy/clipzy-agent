# CLIPZY AI Server 배포 가이드

CLIPZY의 AI 추천 서버 (FastAPI) 배포 문서입니다.

## 📋 시스템 요구사항

### 최소 사양
- **CPU:** 2 vCPU
- **RAM:** 4GB
- **Storage:** 20GB SSD
- **OS:** Ubuntu 22.04 LTS (또는 Amazon Linux 2023)

### 권장 사양
- **CPU:** 4 vCPU
- **RAM:** 8GB
- **Storage:** 30GB SSD

### 필수 소프트웨어
- Docker 24+ & Docker Compose 2+
- 또는 Python 3.12+ (직접 실행 시)

## 🔑 필요한 API 키

배포 전에 다음 API 키를 준비하세요:

1. **OpenAI API Key**
   - https://platform.openai.com/api-keys
   - GPT-4o-mini 모델 접근 권한 필요

2. **YouTube Data API v3 Key**
   - https://console.cloud.google.com/
   - YouTube Data API v3 활성화 필요
   - 일일 quota: 10,000 units (기본)

## 🚀 배포 방법

### 방법 A: Docker Compose (권장)

#### 1단계: 코드 클론
\`\`\`bash
git clone <repository-url>
cd clipzy-agent
\`\`\`

#### 2단계: 환경 변수 설정
\`\`\`bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (API 키 등)
nano .env
\`\`\`

**.env 파일 예시:**
\`\`\`env
OPENAI_API_KEY=sk-...
YOUTUBE_API_KEY=AIza...
APP_ENV=production
LOG_LEVEL=INFO
\`\`\`

#### 3단계: 실행
\`\`\`bash
# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f fastapi

# 상태 확인
docker-compose ps
\`\`\`

#### 4단계: 헬스체크
\`\`\`bash
# API 응답 확인
curl http://localhost:8000/api/v1/health

# Swagger UI
# 브라우저: http://<EC2-IP>:8000/docs
\`\`\`

### 방법 B: 직접 실행 (개발용)

\`\`\`bash
# 1. Python 가상환경
python3.12 -m venv venv
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. Redis, Qdrant 별도 실행 필요
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 6333:6333 qdrant/qdrant:latest

# 4. FastAPI 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
\`\`\`

## 🌐 네트워크 설정

### AWS Security Group

**Inbound Rules:**

| Port | Protocol | Source | 설명 |
|------|----------|--------|------|
| 8000 | TCP | Spring 서버 IP | FastAPI API |
| 22 | TCP | 관리자 IP | SSH |
| 6379 | TCP | localhost | Redis (내부) |
| 6333 | TCP | localhost | Qdrant (내부) |

**주의:** 6379, 6333 포트는 절대 외부에 노출하지 마세요!

### Spring 서버 연동

Spring 서버의 `application.yml` 수정:
\`\`\`yaml
ai:
  server:
    url: http://<EC2-Public-IP>:8000
\`\`\`

## 📊 모니터링

### 로그 확인
\`\`\`bash
# 실시간 로그
docker-compose logs -f fastapi

# 최근 100줄
docker-compose logs --tail=100 fastapi

# 특정 시간 이후
docker-compose logs --since="1h" fastapi
\`\`\`

### 리소스 확인
\`\`\`bash
# 컨테이너 상태
docker-compose ps

# 리소스 사용량
docker stats
\`\`\`

## 🔧 트러블슈팅

### 1. OpenAI API 에러
**증상:** `openai.AuthenticationError`
**해결:** `.env`의 `OPENAI_API_KEY` 확인

### 2. YouTube Quota 초과
**증상:** `HttpError 403: quota exceeded`
**해결:**
- 새 API 키 발급
- 또는 다음 날까지 대기 (자정 PST 리셋)

### 3. Redis 연결 실패
**증상:** `redis.ConnectionError`
**해결:**
\`\`\`bash
# Redis 상태 확인
docker-compose ps redis

# Redis 재시작
docker-compose restart redis
\`\`\`

### 4. Qdrant 데이터 손실
**증상:** 사용자 프로필 사라짐
**해결:** 볼륨 확인
\`\`\`bash
docker volume ls
docker volume inspect clipzy-agent_qdrant_data
\`\`\`

### 5. 메모리 부족
**증상:** OOM Kill
**해결:**
- EC2 인스턴스 업그레이드
- 또는 Redis maxmemory 제한

## 🔄 업데이트 방법

\`\`\`bash
# 1. 최신 코드 pull
git pull origin main

# 2. 재빌드 & 재시작
docker-compose up -d --build

# 3. 로그 확인
docker-compose logs -f fastapi
\`\`\`

## 🛑 중지 & 삭제

\`\`\`bash
# 중지 (데이터 유지)
docker-compose down

# 완전 삭제 (데이터 포함)
docker-compose down -v
\`\`\`

## 📞 문의

배포 관련 문의: now.presentk@gmail.com