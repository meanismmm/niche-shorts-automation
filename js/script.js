// =============================================
// 카테고리 설정
// =============================================
const CATEGORIES = {
  pet:        { name: '반려동물',      type: 'pain', emoji: '🐾' },
  single:     { name: '1인가구 생활',  type: 'pain', emoji: '🏠' },
  sleep:      { name: '수면/휴식',     type: 'pain', emoji: '😴' },
  homeoffice: { name: '홈오피스',      type: 'pain', emoji: '💻' },
  kitchen:    { name: '주방/요리',     type: 'pain', emoji: '🍳' },
  gadget:     { name: '신박한 아이템', type: 'wow',  emoji: '✨' },
};

// =============================================
// PAIN형 프롬프트 생성
// =============================================
function buildPainPrompt(product, category, target) {
  return `당신은 쇼츠/릴스 전문 마케팅 카피라이터입니다.

상품: ${product}
카테고리: ${category}
타겟: ${target || '20~40대 일반 소비자'}
영상 길이: 15~30초

아래 3단계로 스크립트를 작성하세요.

STEP 1 — PAIN 추출
이 상품을 아직 모르는 타겟이 일상에서 겪는 구체적 불편함 5가지를 추론하세요.
조건:
- 특정 시간/장소/상황 포함 (예: "새벽에", "출근 직전에")
- 감정 포함 (예: "짜증났다", "불안했다")
- 상품명이나 카테고리가 연상되지 않을 것

STEP 2 — 가장 강한 PAIN 1개 선택
공감도 최고, 감정 강도 최고, 상황이 구체적인 것 선택

STEP 3 — 스크립트 작성
반드시 아래 JSON 형식으로만 응답하세요:

{
  "pain_selected": "선택한 PAIN 한 줄 설명",
  "opening": "오프닝 질문 (15자 이내, 구체적 상황 포함)",
  "empathy": "공감 멘트 2~3문장 (저도 그랬습니다 + 상황 묘사)",
  "solution": "해결책 3~4문장 (상품이 어떻게 해결하는지, 상품명 자연스럽게 1회만)",
  "cta": "행동 유도 1~2문장 (설명란 링크 유도)",
  "hashtags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "youtube_title": "유튜브 제목 (클릭율 높게, 30자 이내)",
  "description": "영상 설명란 텍스트 (SEO 최적화, 쿠팡파트너스 고지 문구 포함)"
}

절대 금지:
- "더 좋은 방법이 있다면 어떨까요?" 같은 뻔한 표현
- 첫 문장에 상품명 언급
- "추천합니다", "강력추천" 같은 광고 티 나는 표현
- JSON 외 다른 텍스트 출력`;
}

// =============================================
// WOW형 프롬프트 생성
// =============================================
function buildWowPrompt(product, target) {
  return `당신은 쇼츠/릴스 전문 마케팅 카피라이터입니다.

상품: ${product}
타겟: ${target || '신기한 것에 관심 많은 20~30대'}
영상 길이: 15~30초

아래 3단계로 스크립트를 작성하세요.

STEP 1 — WOW 포인트 추출
이 상품에서 처음 보는 사람이 "이게 진짜야?" 라고 반응할 요소 3가지:
- 크기/무게/가격의 반전
- 기능의 의외성
- 눈으로 봐야 믿기지 않는 요소

STEP 2 — 가장 강한 WOW 1개 선택
영상으로 보여줬을 때 엄지 멈춤 효과가 가장 클 것

STEP 3 — 스크립트 작성
반드시 아래 JSON 형식으로만 응답하세요:

{
  "wow_selected": "선택한 WOW 포인트 한 줄 설명",
  "opening": "호기심 오프닝 (20자 이내, 상품명 직접 언급 금지)",
  "proof": "증명 멘트 2~3문장 (실제 스펙/특징을 구체적 수치로)",
  "usage": "활용 장면 2~3문장 (이걸로 뭘 할 수 있는지 구체적으로)",
  "cta": "행동 유도 1~2문장 (설명란 링크 유도)",
  "hashtags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "youtube_title": "유튜브 제목 (클릭율 높게, 30자 이내)",
  "description": "영상 설명란 텍스트 (SEO 최적화, 쿠팡파트너스 고지 문구 포함)"
}

절대 금지:
- 상품명을 오프닝에 직접 언급
- 뻔한 리뷰 형식
- JSON 외 다른 텍스트 출력`;
}

// =============================================
// Claude API 호출
// =============================================
async function generateScript(product, categoryKey, target, coupangLink) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) {
    showError('Claude API 키를 설정해주세요');
    return null;
  }

  const category = CATEGORIES[categoryKey];
  const prompt = category.type === 'wow'
    ? buildWowPrompt(product, target)
    : buildPainPrompt(product, category.name, target);

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': claudeKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1500,
        messages: [{ role: 'user', content: prompt }]
      })
    });

    const data = await response.json();
    if (data.error) throw new Error(data.error.message);

    const text = data.content[0].text;
    const clean = text.replace(/```json|```/g, '').trim();
    const script = JSON.parse(clean);
    script.product = product;
    script.category = category;
    script.coupangLink = coupangLink;
    script.type = category.type;
    script.createdAt = new Date().toISOString();
    return script;

  } catch (err) {
    showError('스크립트 생성 실패: ' + err.message);
    return null;
  }
}

// =============================================
// 컷 속도 규칙
// =============================================
const CUT_RULES = {
  pain: {
    opening:  { min: 0.8, max: 1.2, speed: 1.15 },
    empathy:  { min: 1.5, max: 2.5, speed: 1.0  },
    solution: { min: 1.0, max: 2.0, speed: 1.0  },
    cta:      { min: 0.8, max: 1.0, speed: 1.0  },
  },
  wow: {
    opening:  { min: 0.5, max: 0.8, speed: 1.2  },
    proof:    { min: 2.0, max: 3.0, speed: 0.8  },
    usage:    { min: 1.0, max: 1.5, speed: 1.05 },
    cta:      { min: 0.8, max: 1.0, speed: 1.0  },
  }
};

// =============================================
// 히스토리 관리
// =============================================
function saveToHistory(script) {
  const history = JSON.parse(localStorage.getItem('script_history') || '[]');
  history.unshift(script);
  localStorage.setItem('script_history', JSON.stringify(history.slice(0, 100)));
}

function loadHistory() {
  return JSON.parse(localStorage.getItem('script_history') || '[]');
}

// =============================================
// UI 유틸리티
// =============================================
function showError(msg) {
  const el = document.getElementById('notification');
  if (!el) return;
  el.textContent = '❌ ' + msg;
  el.className = 'notification error show';
  setTimeout(() => el.classList.remove('show'), 4000);
}

function showSuccess(msg) {
  const el = document.getElementById('notification');
  if (!el) return;
  el.textContent = '✅ ' + msg;
  el.className = 'notification success show';
  setTimeout(() => el.classList.remove('show'), 3000);
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text);
  showSuccess('클립보드에 복사됐습니다');
}
