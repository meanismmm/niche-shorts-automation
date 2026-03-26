// =============================================
// v2.0 — 카테고리 + 상품 분석 기반 스크립트
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
// 1단계: 카테고리별 상품 추천
// =============================================
async function recommendProducts(categoryKey) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) { showError('Claude API 키를 설정해주세요'); return null; }

  const category = CATEGORIES[categoryKey];

  const prompt = `당신은 쿠팡파트너스 전문가입니다.
카테고리: ${category.name} (${category.emoji})

이 카테고리에서 쿠팡파트너스로 수익을 내기 좋은 상품 10개를 추천해주세요.

선정 기준:
- 실제 쿠팡에서 판매 중인 상품
- 리뷰 1000개 이상 인기 상품
- 가격대 1만원~10만원 (충동구매 가능)
- 쇼츠/릴스 영상으로 만들기 좋은 시각적 상품
- 파트너스 수수료 높은 카테고리 우선

반드시 아래 JSON 형식으로만 응답 (JSON 외 텍스트 금지):

{
  "products": [
    {
      "rank": 1,
      "name": "상품명",
      "price_range": "가격대 (예: 2~3만원)",
      "why": "추천 이유 한 줄 (쇼츠 영상으로 만들기 좋은 이유)",
      "pain_or_wow": "pain 또는 wow",
      "search_keyword": "쿠팡 검색 키워드"
    }
  ]
}`;

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': claudeKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 2000,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('JSON 파싱 실패');
    return JSON.parse(match[0]);
  } catch(err) {
    showError('상품 추천 실패: ' + err.message);
    return null;
  }
}

// =============================================
// 2단계: 쿠팡 상세페이지 분석
// =============================================
async function analyzeProduct(url, productName) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) { showError('Claude API 키를 설정해주세요'); return null; }

  let pageContent = '';
  if (url) {
    try {
      const res = await fetch(`https://api.allorigins.win/get?url=${encodeURIComponent(url)}`);
      const data = await res.json();
      if (data.contents) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(data.contents, 'text/html');
        ['script','style','nav','header','footer'].forEach(tag => {
          doc.querySelectorAll(tag).forEach(el => el.remove());
        });
        pageContent = doc.body?.innerText?.slice(0, 3000) || '';
      }
    } catch(e) {
      console.log('페이지 로드 실패, 상품명 기반 분석으로 전환');
    }
  }

  const prompt = `당신은 쿠팡파트너스 마케팅 전문가입니다.

상품명: ${productName}
${url ? `쿠팡 URL: ${url}` : ''}
${pageContent ? `페이지 내용:\n${pageContent}` : ''}

위 상품을 분석해서 쇼츠/릴스 마케팅에 필요한 정보를 추출해주세요.
페이지 내용이 없으면 상품명만으로 최대한 분석해주세요.

반드시 아래 JSON 형식으로만 응답:

{
  "product_name": "정확한 상품명",
  "core_function": "핵심 기능 한 줄",
  "key_specs": ["스펙1", "스펙2", "스펙3"],
  "target_customer": "주요 타겟 고객층",
  "main_pains": ["이 상품 없이 겪는 불편함1", "불편함2", "불편함3"],
  "wow_points": ["놀라운 점1", "놀라운 점2"],
  "hook_keywords": ["후킹에 쓸 키워드1", "키워드2", "키워드3"],
  "recommended_type": "pain 또는 wow",
  "price_appeal": "가격 매력 포인트 (예: 배달음식 한 번 값으로)",
  "visual_scenes": ["영상으로 보여주면 좋은 장면1", "장면2", "장면3"]
}`;

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
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
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('JSON 파싱 실패');
    return JSON.parse(match[0]);
  } catch(err) {
    showError('상품 분석 실패: ' + err.message);
    return null;
  }
}

// =============================================
// 3단계: 분석 데이터 기반 스크립트 생성
// =============================================
async function generateScriptFromAnalysis(analysis, categoryKey, coupangLink) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) { showError('Claude API 키를 설정해주세요'); return null; }

  const category = CATEGORIES[categoryKey];
  const isPain = analysis.recommended_type !== 'wow';
  const prompt = isPain
    ? buildPainPromptV2(analysis, category, coupangLink)
    : buildWowPromptV2(analysis, category, coupangLink);

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
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
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('JSON 파싱 실패');
    const script = JSON.parse(match[0]);
    script.product     = analysis.product_name;
    script.category    = category;
    script.coupangLink = coupangLink;
    script.type        = isPain ? 'pain' : 'wow';
    script.analysis    = analysis;
    script.createdAt   = new Date().toISOString();
    return script;
  } catch(err) {
    showError('스크립트 생성 실패: ' + err.message);
    return null;
  }
}

function buildPainPromptV2(analysis, category, link) {
  return `당신은 대한민국 최고의 쇼츠/릴스 마케팅 카피라이터입니다.

[상품 분석 데이터]
상품명: ${analysis.product_name}
핵심 기능: ${analysis.core_function}
주요 스펙: ${analysis.key_specs?.join(', ')}
타겟 고객: ${analysis.target_customer}
주요 PAIN: ${analysis.main_pains?.join(' / ')}
후킹 키워드: ${analysis.hook_keywords?.join(', ')}
가격 매력: ${analysis.price_appeal}
시각 장면: ${analysis.visual_scenes?.join(' / ')}

위 분석 데이터를 100% 활용해서 15~30초 PAIN형 쇼츠 스크립트를 작성하세요.

절대 금지:
- 시간대 표현 (늦은 밤, 새벽, 아침, 저녁)
- 막연한 표현 (항상, 매번, 늘, 자꾸)
- 광고 티 나는 표현 (추천합니다, 강력추천)
- 첫 문장에 상품명 언급
- JSON 외 텍스트 출력

반드시 아래 JSON 형식으로만 응답:
{
  "pain_selected": "선택한 PAIN 한 줄",
  "opening": "후킹 질문 (20자 이내, 구체적 행동 상황, 상품명 금지)",
  "empathy": "공감 2~3문장 (구체적 실패 상황, 감정 묘사)",
  "solution": "해결 3~4문장 (상품명 1회, 스펙/수치 포함)",
  "cta": "행동 유도 1~2문장 (설명란 링크 언급)",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자나 반전 포함)",
  "description": "설명란 텍스트 (SEO 최적화)\\n\\n파트너스 링크: ${link || '[쿠팡파트너스 링크 입력]'}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."
}`;
}

function buildWowPromptV2(analysis, category, link) {
  return `당신은 대한민국 최고의 쇼츠/릴스 마케팅 카피라이터입니다.

[상품 분석 데이터]
상품명: ${analysis.product_name}
핵심 기능: ${analysis.core_function}
WOW 포인트: ${analysis.wow_points?.join(' / ')}
후킹 키워드: ${analysis.hook_keywords?.join(', ')}
가격 매력: ${analysis.price_appeal}
시각 장면: ${analysis.visual_scenes?.join(' / ')}

위 분석 데이터를 100% 활용해서 15~30초 WOW형 쇼츠 스크립트를 작성하세요.

절대 금지:
- 오프닝에 상품명 직접 언급
- 뻔한 리뷰 형식
- JSON 외 텍스트 출력

반드시 아래 JSON 형식으로만 응답:
{
  "wow_selected": "선택한 WOW 포인트",
  "opening": "호기심 오프닝 (20자 이내, 반전/충격, 상품명 금지)",
  "proof": "증명 2~3문장 (구체적 수치, 스펙, 비교)",
  "usage": "활용 2~3문장 (구체적 사용 장면)",
  "cta": "행동 유도 1~2문장",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자/반전 포함)",
  "description": "설명란 텍스트 (SEO 최적화)\\n\\n파트너스 링크: ${link || '[쿠팡파트너스 링크 입력]'}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."
}`;
}

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
