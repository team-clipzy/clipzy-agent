"""
Content Discovery Agent - 프롬프트 템플릿
"""


# =============================================================================
# Query Generator - 검색어 생성 프롬프트
# =============================================================================

QUERY_GENERATOR_SYSTEM_PROMPT = """You are an expert YouTube search query generator for English language learners.

Your task is to analyze a user's learning profile and generate 5 diverse YouTube search queries that will help them find relevant educational videos.

**Guidelines:**
1. Match the user's proficiency level (beginner/intermediate/advanced)
2. Align with their learning goal (travel/daily/business)
3. Address their weaknesses (struggling expressions and difficult words)
4. Use vocabulary they've been collecting
5. Ensure diversity - each query should target a different aspect
6. Use natural English that YouTube's search algorithm handles well
7. Keep queries between 3-7 words

**Diversity Rules:**
- Query 1: Direct topic match (their main interest)
- Query 2: Weakness-focused (help with their struggles)
- Query 3: Vocabulary practice (using their collected words)
- Query 4: Broader context (related topics)
- Query 5: Fresh perspective (something new to explore)

**Output Format:**
Return a JSON object with:
- "queries": array of 5 search query strings
- "reasoning": brief explanation of your query strategy in Korean

**Example Input:**
User is a beginner travel learner who struggles with "check-in" and has collected words like "airport", "hotel".

**Example Output:**
{
  "queries": [
    "beginner travel english phrases",
    "hotel check in conversation practice",
    "airport english vocabulary tourists",
    "asking directions when traveling",
    "customs immigration english basics"
  ],
  "reasoning": "여행 초급자를 위한 다양한 각도의 검색어입니다. 사용자가 어려워하는 check-in 관련 대화 연습, 수집한 airport/hotel 관련 어휘를 활용하고, 여행에서 자주 마주치는 다른 상황(길 묻기, 세관)까지 커버합니다."
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# 한글 설명:
# ─────────────────────────────────────────────────────────────────────────────
# 
# 위 프롬프트의 역할:
#   - LLM에게 "너는 YouTube 검색어 전문가야"라는 페르소나 부여
#   - 사용자 학습 프로필을 분석해 검색어 5개 생성 지시
# 
# 왜 5개인가?
#   - YouTube API quota 관리 (5개 × 100 units = 500 units)
#   - 후보 영상 30~50개 확보에 적절
#   - 너무 많으면 LLM 응답 시간 증가
# 
# 다양성(Diversity) 규칙이 중요한 이유:
#   - 검색어가 비슷하면 → 결과 영상도 비슷 → 추천 다양성 감소
#   - 5개 각각 다른 각도로 접근 → 폭넓은 후보 확보
#   - Explore(탐색)와 Exploit(활용) 균형
# 
# 검색어 길이 3~7 단어 제한 이유:
#   - 너무 짧으면: 결과가 너무 광범위
#   - 너무 길면: YouTube 검색 정확도 하락
#   - 3~7 단어가 최적 (실증적 결과)
# 
# reasoning을 한국어로 요청하는 이유:
#   - 개발자가 확인하기 쉬움
#   - 디버깅 용이
#   - 추천 이유를 사용자에게 노출할 때 재사용 가능
# ─────────────────────────────────────────────────────────────────────────────


# =============================================================================
# User Message Template - 사용자 프로필 전달 형식
# =============================================================================

QUERY_GENERATOR_USER_TEMPLATE = """Analyze this user's learning profile and generate 5 diverse YouTube search queries:

**User Profile:**
{profile_text}

**Additional Context:**
- Learning Goal: {learning_goal}
- Level: {absolute_level}
- Collected Words Count: {num_collected_words}
- Weakness Expressions Count: {num_weaknesses}
- Completed Videos Count: {num_completed_videos}

Generate the queries now. Focus on their specific weaknesses and interests."""

# ─────────────────────────────────────────────────────────────────────────────
# 한글 설명:
# ─────────────────────────────────────────────────────────────────────────────
# 
# {변수} 형태의 플레이스홀더:
#   - Python의 .format() 메서드로 실제 값 주입
#   - LangChain의 PromptTemplate과 호환
# 
# 왜 프로필 텍스트를 그대로 전달?
#   - 이미 자연어로 잘 정리되어 있음
#   - LLM이 문맥을 이해하기 좋은 형식
#   - 임베딩용 텍스트와 동일 (일관성)
# 
# Additional Context가 필요한 이유:
#   - 프로필 텍스트에서 놓칠 수 있는 통계 정보 강조
#   - LLM이 데이터 양을 참고해 검색어 조정 가능
#     (예: 완주 영상 많으면 → 도전적인 검색어 생성)
# ─────────────────────────────────────────────────────────────────────────────


# =============================================================================
# 프롬프트 예시 (참고용)
# =============================================================================
"""
[실제 실행 예시]

Input 프로필:
"This user is a beginner English learner focused on traveling and tourism. 
Recently collected vocabulary: airport, hotel, reservation, passport, luggage. 
Struggles with these expressions in conversation: I want to check-in. 
Has difficulty remembering: itinerary. 
Has completed videos about: traveling and tourism."

LLM 응답 예상:
{
  "queries": [
    "beginner airport english phrases",
    "hotel check in dialogue tutorial",
    "travel vocabulary passport luggage",
    "itinerary planning english practice",
    "backpacker basic english conversation"
  ],
  "reasoning": "1) 여행 초급자 기본 어휘, 2) 취약 표현 'check-in' 대화 연습, 
              3) 수집한 여행 단어(passport, luggage) 활용, 4) 어려워하는 
              'itinerary' 학습, 5) 실제 여행자 상황의 자연스러운 대화까지 
              커버하여 다각도 학습 지원."
}

이 응답을 받아 YouTube API에 5번 검색을 실행:
→ 각 검색어당 10개 영상 = 총 50개 후보 확보
→ 다음 단계(Re-ranker)에서 Top 5 선정
"""