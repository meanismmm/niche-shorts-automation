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
// PAIN형 프롬프트 생성 (강화버전)
// =============================================
function buildPainPrompt(product, category, target) {
  return `당신은 대한민국 최고의 쇼츠/릴스 마케팅 카피라이터입니다.
엄지손가락을 멈추게 하는 강렬한 후킹 스크립트를 작성하세요.

상품: ${product}
카테고리: ${category}
타겟: ${target || '20~40대 일반 소비자'}
영상 길이: 15~30초

STEP 1 — PAIN 추출 (5가지)
이 상품 없이 타겟이 겪는 구체적 불편함 5가지:
- 반드시 특정 행동/상황 중심으로 (예: "설거지하다가", "요리하다가")
- 감정이 구체적으로 드러날 것 (짜증, 당황, 포기, 실망)
- 시간대(밤/새벽/아침) 표현 절대 금지
- "항상", "매번", "늘" 같은 막연한 표현 금지

STEP 2 — 최강 PAIN 1개 선택
- 가장 많은 타겟이 "맞아 나도!"라고 반응할 것
- 영상으로 보여주면 공감이 폭발할 것

STEP 3 — 스크립트 작성
반드시 아래 JSON 형식으로만 응답:

{
  "pain_selected": "선택한 PAIN 한 줄",
  "opening": "후킹 질문 (20자 이내, 구체적 행동 상황, 시간대 표현 금지)",
  "empathy": "공감 2~3문장 (나도 그랬다 + 구체적 실패 상황 묘사)",
  "solution": "해결 3~4문장 (상품명 1회, 구체적 수치/변화 포함)",
  "cta": "행동 유도 1~2문장 (설명란 링크)",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자나 반전 포함)",
  "description": "설명란 (SEO 최적화 + 쿠팡파트너스 고지)"
}

절대 금지:
- 시간대 표현: 늦은 밤, 새벽, 저녁, 아침 등
- 막연한 표현: 항상, 매번, 늘, 자꾸
- 광고 티: 추천합니다, 강력추천, 최고의
- 첫 문장에 상품명 언급
- JSON 외 텍스트 출력`;
}

// =============================================
// WOW형 프롬프트 생성
// =============================================
function buildWowPrompt(product, target) {
  return `당신은 대한민국 최고의 쇼츠/릴스 마케팅 카피라이터입니다.

상품: ${product}
타겟: ${target || '신기한 것에 관심 많은 20~30대'}
영상 길이: 15~30초

STEP 1 — WOW 포인트 3가지
- 크기/무게/가격의 반전
- 기능의 의외성 (상식을 깨는 것)
- 눈으로 봐야 믿기지 않는 스펙

STEP 2 — 최강 WOW 1개 선택
영상으로 보여줬을 때 "헐 진짜?" 반응이 나올 것

STEP 3 — 스크립트 작성
반드시 아래 JSON 형식으로만 응답:

{
  "wow_selected": "선택한 WOW 포인트",
  "opening": "호기심 오프닝 (20자 이내, 상품명 금지, 반전/충격 표현)",
  "proof": "증명 2~3문장 (구체적 수치, 비교, 실제 스펙)",
  "usage": "활용 2~3문장 (구체적 사용 장면)",
  "cta": "행동 유도 1~2문장",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자/반전 포함)",
  "description": "설명란 (SEO 최적화 + 쿠팡파트너스 고지)"
}

절대 금지:
- 오프닝에 상품명 직접 언급
- 뻔한 리뷰 형식
- JSON 외 텍스트 출력`;
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
