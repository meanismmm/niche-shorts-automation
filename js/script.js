// =============================================
// v2.1 — 상품 분석 + Pixabay + 10구간 소스 수집
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
// 10구간 설계 (PAIN/WOW별)
// =============================================
function getSections(type) {
  if (type === 'wow') {
    return [
      { key: 'opening_1',  label: '⚡ 오프닝 1 (0~2초)',   scriptKey: 'opening',  desc: '첫 번째 충격 장면' },
      { key: 'opening_2',  label: '⚡ 오프닝 2 (2~4초)',   scriptKey: 'opening',  desc: '두 번째 충격 장면' },
      { key: 'proof_1',    label: '🔍 증명 1 (4~8초)',     scriptKey: 'proof',    desc: '스펙/수치 클로즈업' },
      { key: 'proof_2',    label: '🔍 증명 2 (8~12초)',    scriptKey: 'proof',    desc: '제품 디테일 샷' },
      { key: 'proof_3',    label: '🔍 증명 3 (12~15초)',   scriptKey: 'proof',    desc: '실제 작동 장면' },
      { key: 'usage_1',    label: '🎯 활용 1 (15~18초)',   scriptKey: 'usage',    desc: '사용 전 상황' },
      { key: 'usage_2',    label: '🎯 활용 2 (18~22초)',   scriptKey: 'usage',    desc: '사용 중 장면' },
      { key: 'usage_3',    label: '🎯 활용 3 (22~25초)',   scriptKey: 'usage',    desc: '사용 후 변화' },
      { key: 'cta_1',      label: '🔗 CTA 1 (25~27초)',    scriptKey: 'cta',      desc: '제품 강조 샷' },
      { key: 'cta_2',      label: '🔗 CTA 2 (27~30초)',    scriptKey: 'cta',      desc: '링크 유도 장면' },
    ];
  } else {
    return [
      { key: 'opening_1',  label: '⚡ 오프닝 1 (0~2초)',   scriptKey: 'opening',  desc: '강렬한 후킹 질문' },
      { key: 'opening_2',  label: '⚡ 오프닝 2 (2~4초)',   scriptKey: 'opening',  desc: '문제 상황 클로즈업' },
      { key: 'empathy_1',  label: '💭 공감 1 (4~8초)',     scriptKey: 'empathy',  desc: '좌절하는 표정/상황' },
      { key: 'empathy_2',  label: '💭 공감 2 (8~12초)',    scriptKey: 'empathy',  desc: '구체적 불편 장면' },
      { key: 'empathy_3',  label: '💭 공감 3 (12~14초)',   scriptKey: 'empathy',  desc: '공감 강화 장면' },
      { key: 'solution_1', label: '✅ 해결 1 (14~18초)',   scriptKey: 'solution', desc: '제품 등장 장면' },
      { key: 'solution_2', label: '✅ 해결 2 (18~22초)',   scriptKey: 'solution', desc: '제품 사용 장면' },
      { key: 'solution_3', label: '✅ 해결 3 (22~25초)',   scriptKey: 'solution', desc: '변화/만족 표정' },
      { key: 'cta_1',      label: '🔗 CTA 1 (25~27초)',    scriptKey: 'cta',      desc: '제품 강조 샷' },
      { key: 'cta_2',      label: '🔗 CTA 2 (27~30초)',    scriptKey: 'cta',      desc: '링크 유도 장면' },
    ];
  }
}

// =============================================
// 소스 검색 링크
// =============================================
function buildSourceSearchLinks(productName) {
  const enc = encodeURIComponent(productName);
  return [
    { label: '알리익스프레스', icon: '🛒', url: `https://www.aliexpress.com/wholesale?SearchText=${enc}` },
    { label: '타오바오',       icon: '🏮', url: `https://s.taobao.com/search?q=${enc}` },
    { label: '1688 (도매)',    icon: '🏭', url: `https://s.1688.com/selloffer/offer_search.htm?keywords=${enc}` },
    { label: 'YouTube 영상',  icon: '▶️', url: `https://www.youtube.com/results?search_query=${enc}+리뷰` },
    { label: 'Google 이미지', icon: '🖼️', url: `https://www.google.com/search?q=${enc}&tbm=isch` },
    { label: '쿠팡 검색',     icon: '🛍️', url: `https://www.coupang.com/np/search?q=${enc}` },
  ];
}

function renderSourceSearchLinks(productName, containerId) {
  const links = buildSourceSearchLinks(productName);
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <div style="margin-top:16px;padding:14px;background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.2);border-radius:10px;">
      <div style="font-size:11px;color:var(--accent3);font-family:'Space Mono',monospace;margin-bottom:10px;">🔍 영상 소스 수집용 검색 링크</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        ${links.map(l=>`
          <a href="${l.url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:8px;background:var(--surface2);border:1px solid var(--border);font-size:12px;color:var(--text);text-decoration:none;transition:all .15s;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
            ${l.icon} ${l.label}
          </a>
        `).join('')}
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:8px;">💡 클릭 후 제품 이미지/영상 저장 → 영상 소스 수집에서 직접 업로드</div>
    </div>
  `;
}

// =============================================
// Pexels 검색
// =============================================
async function fetchPexelsVideos(keyword, perPage = 3) {
  const key = CONFIG.get(CONFIG.KEYS.PEXELS);
  if (!key) return [];
  try {
    const res = await fetch(
      `https://api.pexels.com/videos/search?query=${encodeURIComponent(keyword)}&per_page=${perPage}&orientation=portrait`,
      { headers: { Authorization: key } }
    );
    const data = await res.json();
    return (data.videos || []).map(v => ({
      id: v.id, thumb: v.image,
      url: v.video_files?.find(f => f.quality === 'sd')?.link || v.video_files?.[0]?.link,
      duration: v.duration, source: 'pexels'
    }));
  } catch { return []; }
}

// =============================================
// Pixabay 검색 (영상 + 이미지)
// =============================================
async function fetchPixabayVideos(keyword, perPage = 3) {
  const key = CONFIG.get(CONFIG.KEYS.PIXABAY);
  if (!key) return [];
  try {
    const res = await fetch(
      `https://pixabay.com/api/videos/?key=${key}&q=${encodeURIComponent(keyword)}&per_page=${perPage}&video_type=film&orientation=vertical`
    );
    const data = await res.json();
    return (data.hits || []).map(v => ({
      id: v.id,
      thumb: v.videos?.tiny?.thumbnail || v.userImageURL,
      url: v.videos?.medium?.url || v.videos?.small?.url,
      duration: v.duration, source: 'pixabay'
    })).filter(v => v.url);
  } catch { return []; }
}

async function fetchPixabayImages(keyword, perPage = 3) {
  const key = CONFIG.get(CONFIG.KEYS.PIXABAY);
  if (!key) return [];
  try {
    const res = await fetch(
      `https://pixabay.com/api/?key=${key}&q=${encodeURIComponent(keyword)}&per_page=${perPage}&image_type=photo&orientation=vertical&safesearch=true`
    );
    const data = await res.json();
    return (data.hits || []).map(img => ({
      id: img.id,
      thumb: img.webformatURL,
      url: img.largeImageURL,
      source: 'pixabay_image'
    }));
  } catch { return []; }
}

// =============================================
// Gemini 이미지 생성
// =============================================
async function generateGeminiImage(prompt) {
  const key = CONFIG.get(CONFIG.KEYS.GEMINI);
  if (!key) return null;
  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key=${key}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { responseModalities: ['TEXT', 'IMAGE'] }
        })
      }
    );
    const data = await res.json();
    if (data.error) { console.error('Gemini 오류:', data.error); return null; }
    const imgPart = data.candidates?.[0]?.content?.parts?.find(p => p.inlineData);
    if (!imgPart) return null;
    return `data:${imgPart.inlineData.mimeType};base64,${imgPart.inlineData.data}`;
  } catch(e) { console.error('Gemini 실패:', e); return null; }
}

// =============================================
// Claude로 구간별 검색 키워드 생성
// =============================================
async function generateSectionKeywords(script, sections) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) return null;

  const product = script.product || '';
  const isWow   = script.type === 'wow';
  const analysis = script.analysis || {};

  const sectionDesc = sections.map(s => `${s.key}: ${s.desc}`).join('\n');

  const prompt = `You are a video search expert for Pexels and Pixabay.
Product: ${product}
Type: ${isWow ? 'WOW' : 'PAIN'}
Main pain: ${(analysis.main_pains || [''])[0]}
Visual scenes: ${(analysis.visual_scenes || []).join(', ')}

For each section below, generate the BEST 2-4 word English search keyword.
Each section MUST have a DIFFERENT keyword. Never repeat.
Return ONLY raw JSON, no markdown.

Sections:
${sectionDesc}

Return format (one key per section):
{${sections.map(s => `"${s.key}":"keyword"`).join(',')}}`;

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': claudeKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
        'anthropic-dangerous-direct-browser-access': 'true'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 400,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const data = await res.json();
    let text = data.content[0].text.replace(/```json/gi, '').replace(/```/g, '').trim();
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('no JSON');
    return JSON.parse(match[0]);
  } catch(e) {
    console.error('키워드 생성 실패:', e);
    // 폴백: 기본 키워드
    const fallback = {};
    sections.forEach(s => { fallback[s.key] = product; });
    return fallback;
  }
}

// =============================================
// 1단계: 상품 추천
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

반드시 아래 JSON 형식으로만 응답:
{
  "products": [
    {
      "rank": 1,
      "name": "상품명",
      "price_range": "가격대",
      "why": "추천 이유 한 줄",
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
// 2단계: 상품 분석
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
    } catch(e) { console.log('페이지 로드 실패'); }
  }

  const prompt = `당신은 쿠팡파트너스 마케팅 전문가입니다.

상품명: ${productName}
${url ? `쿠팡 URL: ${url}` : ''}
${pageContent ? `페이지 내용:\n${pageContent}` : ''}

반드시 아래 JSON 형식으로만 응답:
{
  "product_name": "정확한 상품명",
  "core_function": "핵심 기능 한 줄",
  "key_specs": ["스펙1", "스펙2", "스펙3"],
  "target_customer": "주요 타겟 고객층",
  "main_pains": ["불편함1", "불편함2", "불편함3"],
  "wow_points": ["놀라운 점1", "놀라운 점2"],
  "hook_keywords": ["키워드1", "키워드2", "키워드3"],
  "recommended_type": "pain 또는 wow",
  "price_appeal": "가격 매력 포인트",
  "visual_scenes": ["장면1", "장면2", "장면3"]
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
// 3단계: 스크립트 생성
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
- 광고 티 (추천합니다, 강력추천)
- 첫 문장 상품명 언급
- JSON 외 텍스트

반드시 아래 JSON 형식으로만 응답:
{
  "pain_selected": "선택한 PAIN 한 줄",
  "opening": "후킹 질문 (20자 이내, 구체적 행동 상황, 상품명 금지, 물음표로 끝날 것)",
  "empathy": "공감 2~3문장 (구체적 실패 상황, 감정 묘사, 짧고 강렬하게)",
  "solution": "해결 3~4문장 (상품명 1회, 스펙/수치 포함, 변화 강조)",
  "cta": "행동 유도 1~2문장 (설명란 링크 언급, 긴박감)",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자나 반전 포함)",
  "description": "설명란 텍스트\\n\\n파트너스 링크: ${link || '[쿠팡파트너스 링크 입력]'}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."
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
- JSON 외 텍스트

반드시 아래 JSON 형식으로만 응답:
{
  "wow_selected": "선택한 WOW 포인트",
  "opening": "호기심 오프닝 (20자 이내, 반전/충격, 상품명 금지, 물음표로 끝날 것)",
  "proof": "증명 2~3문장 (구체적 수치, 스펙, 비교, 짧고 강렬하게)",
  "usage": "활용 2~3문장 (구체적 사용 장면, 변화 강조)",
  "cta": "행동 유도 1~2문장 (긴박감)",
  "hashtags": ["태그1","태그2","태그3","태그4","태그5"],
  "youtube_title": "제목 (30자 이내, 숫자/반전 포함)",
  "description": "설명란 텍스트\\n\\n파트너스 링크: ${link || '[쿠팡파트너스 링크 입력]'}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."
}`;
}

// =============================================
// 히스토리
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
// UI 유틸
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
