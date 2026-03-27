// =============================================
// v3.0 — 쿠팡 이미지 자동 분류 + 구간 배치
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
// 쿠팡 미디어 추출
// =============================================
async function extractCoupangMedia(url) {
  if (!url) return { videos: [], images: [] };
  console.log('쿠팡 미디어 추출:', url);

  const proxies = [
    `https://api.allorigins.win/get?url=${encodeURIComponent(url)}`,
    `https://corsproxy.io/?${encodeURIComponent(url)}`,
  ];

  let html = '';
  for (const proxy of proxies) {
    try {
      const res = await fetch(proxy, { signal: AbortSignal.timeout(12000) });
      const data = await res.json();
      html = data.contents || data.body || '';
      if (html.length > 1000) break;
    } catch(e) { console.log('프록시 실패:', e.message); }
  }

  if (!html) return { videos: [], images: [] };

  const videos = [];
  const images = [];
  const seenImgs = new Set();

  // 영상 추출
  const mp4Matches = html.matchAll(/https?:\/\/[^"'\s]+\.mp4[^"'\s]*/g);
  for (const m of mp4Matches) {
    const u = m[0].replace(/&amp;/g, '&');
    if (!videos.find(v => v.url === u)) videos.push({ url: u, type: 'mp4', thumb: null });
  }
  const ytMatches = html.matchAll(/(?:youtube\.com\/embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/g);
  for (const m of ytMatches) {
    const vid = m[1];
    videos.push({ url: `https://www.youtube.com/watch?v=${vid}`, type: 'youtube', thumb: `https://img.youtube.com/vi/${vid}/maxresdefault.jpg` });
  }

  // 이미지 추출 (쿠팡 CDN 패턴)
  const imgPatterns = [
    /https?:\/\/thumbnail[^"'\s]+\.(?:jpg|jpeg|png|webp)[^"'\s]*/g,
    /https?:\/\/[^"'\s]*coupangcdn[^"'\s]*\.(?:jpg|jpeg|png|webp)[^"'\s]*/g,
    /https?:\/\/[^"'\s]*itemcdn[^"'\s]*\.(?:jpg|jpeg|png|webp)[^"'\s]*/g,
    /"imageUrl"\s*:\s*"([^"]+)"/g,
  ];
  for (const pattern of imgPatterns) {
    const matches = html.matchAll(pattern);
    for (const m of matches) {
      let imgUrl = (m[1] || m[0]).replace(/&amp;/g, '&').replace(/\\/g, '');
      if (!imgUrl.startsWith('http')) continue;
      if (imgUrl.includes('icon') || imgUrl.includes('logo') || imgUrl.includes('badge')) continue;
      if (seenImgs.has(imgUrl)) continue;
      seenImgs.add(imgUrl);
      images.push({ url: imgUrl, thumb: imgUrl });
      if (images.length >= 20) break;
    }
    if (images.length >= 20) break;
  }

  console.log(`추출 완료 — 영상: ${videos.length}개, 이미지: ${images.length}개`);
  return { videos, images };
}

// =============================================
// 10구간 정의
// =============================================
function getSections(type) {
  if (type === 'wow') {
    return [
      { key: 'opening_1',  label: '⚡ 오프닝 1',   imgType: 'opening',  desc: '첫 충격 장면' },
      { key: 'opening_2',  label: '⚡ 오프닝 2',   imgType: 'opening',  desc: '제품 첫 등장' },
      { key: 'proof_1',    label: '🔍 증명 1',     imgType: 'proof',    desc: '스펙 인포그래픽' },
      { key: 'proof_2',    label: '🔍 증명 2',     imgType: 'proof',    desc: '수치/비교' },
      { key: 'proof_3',    label: '🔍 증명 3',     imgType: 'proof',    desc: '기능 설명' },
      { key: 'usage_1',    label: '🎯 활용 1',     imgType: 'solution', desc: '사용 전' },
      { key: 'usage_2',    label: '🎯 활용 2',     imgType: 'solution', desc: '사용 중' },
      { key: 'usage_3',    label: '🎯 활용 3',     imgType: 'solution', desc: '사용 후' },
      { key: 'cta_1',      label: '🔗 CTA 1',      imgType: 'cta',      desc: '제품 강조' },
      { key: 'cta_2',      label: '🔗 CTA 2',      imgType: 'cta',      desc: '링크 유도' },
    ];
  } else {
    return [
      { key: 'opening_1',  label: '⚡ 오프닝 1',   imgType: 'opening',  desc: '강렬한 후킹' },
      { key: 'opening_2',  label: '⚡ 오프닝 2',   imgType: 'opening',  desc: '문제 상황' },
      { key: 'empathy_1',  label: '💭 공감 1',     imgType: 'empathy',  desc: '좌절 장면' },
      { key: 'empathy_2',  label: '💭 공감 2',     imgType: 'empathy',  desc: '불편 클로즈업' },
      { key: 'empathy_3',  label: '💭 공감 3',     imgType: 'empathy',  desc: '공감 강화' },
      { key: 'solution_1', label: '✅ 해결 1',     imgType: 'solution', desc: '제품 등장' },
      { key: 'solution_2', label: '✅ 해결 2',     imgType: 'solution', desc: '제품 사용' },
      { key: 'solution_3', label: '✅ 해결 3',     imgType: 'solution', desc: '변화/만족' },
      { key: 'cta_1',      label: '🔗 CTA 1',      imgType: 'cta',      desc: '제품 강조' },
      { key: 'cta_2',      label: '🔗 CTA 2',      imgType: 'cta',      desc: '링크 유도' },
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
  const el = document.getElementById(containerId);
  if (!el) return;
  const links = buildSourceSearchLinks(productName);
  el.innerHTML = `
    <div style="margin-top:14px;padding:14px;background:rgba(245,158,11,.05);border:1px solid rgba(245,158,11,.2);border-radius:10px;">
      <div style="font-size:11px;color:var(--accent3);font-family:'Space Mono',monospace;margin-bottom:10px;">🔍 소스 수집용 링크</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        ${links.map(l=>`<a href="${l.url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:8px;background:var(--surface2);border:1px solid var(--border);font-size:12px;color:var(--text);text-decoration:none;" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">${l.icon} ${l.label}</a>`).join('')}
      </div>
    </div>`;
}

// =============================================
// 상품 추천
// =============================================
async function recommendProducts(categoryKey) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) { showError('Claude API 키를 설정해주세요'); return null; }
  const category = CATEGORIES[categoryKey];
  const prompt = `당신은 쿠팡파트너스 전문가입니다. 카테고리: ${category.name}
이 카테고리에서 쿠팡파트너스 수익화에 좋은 상품 10개를 추천해주세요.
선정 기준: 실제 쿠팡 판매 상품, 리뷰 1000개 이상, 가격 1~10만원, 쇼츠 영상으로 만들기 좋은 시각적 상품
반드시 아래 JSON 형식으로만 응답:
{"products":[{"rank":1,"name":"상품명","price_range":"가격대","why":"추천 이유 한 줄","pain_or_wow":"pain 또는 wow","search_keyword":"쿠팡 검색 키워드"}]}`;
  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type':'application/json','x-api-key':claudeKey,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true' },
      body: JSON.stringify({ model:'claude-sonnet-4-20250514', max_tokens:2000, messages:[{role:'user',content:prompt}] })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    return JSON.parse(text.match(/\{[\s\S]*\}/)[0]);
  } catch(e) { showError('상품 추천 실패: '+e.message); return null; }
}

// =============================================
// 상품 분석
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
        const doc = new DOMParser().parseFromString(data.contents, 'text/html');
        ['script','style','nav','header','footer'].forEach(t => doc.querySelectorAll(t).forEach(e => e.remove()));
        pageContent = doc.body?.innerText?.slice(0, 3000) || '';
      }
    } catch(e) { console.log('페이지 로드 실패'); }
  }
  const prompt = `당신은 쿠팡파트너스 마케팅 전문가입니다.
상품명: ${productName}${url?`\n쿠팡 URL: ${url}`:''}${pageContent?`\n페이지 내용:\n${pageContent}`:''}
반드시 아래 JSON 형식으로만 응답:
{"product_name":"상품명","core_function":"핵심 기능 한 줄","key_specs":["스펙1","스펙2","스펙3"],"target_customer":"타겟 고객층","main_pains":["불편함1","불편함2","불편함3"],"wow_points":["놀라운 점1","놀라운 점2"],"hook_keywords":["키워드1","키워드2","키워드3"],"recommended_type":"pain 또는 wow","price_appeal":"가격 매력 포인트","visual_scenes":["장면1","장면2","장면3"]}`;
  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type':'application/json','x-api-key':claudeKey,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true' },
      body: JSON.stringify({ model:'claude-sonnet-4-20250514', max_tokens:1500, messages:[{role:'user',content:prompt}] })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    return JSON.parse(text.match(/\{[\s\S]*\}/)[0]);
  } catch(e) { showError('상품 분석 실패: '+e.message); return null; }
}

// =============================================
// 스크립트 생성
// =============================================
async function generateScriptFromAnalysis(analysis, categoryKey, coupangLink) {
  const claudeKey = CONFIG.get(CONFIG.KEYS.CLAUDE);
  if (!claudeKey) { showError('Claude API 키를 설정해주세요'); return null; }
  const category = CATEGORIES[categoryKey];
  const isPain   = analysis.recommended_type !== 'wow';
  const link     = coupangLink || '[쿠팡파트너스 링크 입력]';

  const base = `당신은 대한민국 최고의 쇼츠/릴스 마케팅 카피라이터입니다.
[상품 분석 데이터]
상품명: ${analysis.product_name}
핵심 기능: ${analysis.core_function}
주요 스펙: ${analysis.key_specs?.join(', ')}
타겟 고객: ${analysis.target_customer}
PAIN: ${analysis.main_pains?.join(' / ')}
WOW: ${analysis.wow_points?.join(' / ')}
후킹 키워드: ${analysis.hook_keywords?.join(', ')}
가격 매력: ${analysis.price_appeal}
시각 장면: ${analysis.visual_scenes?.join(' / ')}

절대 금지: 시간대 표현, 막연한 표현, 광고 티, 첫 문장 상품명, JSON 외 텍스트`;

  const prompt = isPain
    ? `${base}\n반드시 아래 JSON으로만 응답:\n{"pain_selected":"선택한 PAIN","opening":"후킹 질문 20자 이내 ?로 끝","empathy":"공감 2~3문장 짧고 강렬","solution":"해결 3~4문장 상품명1회 수치포함","cta":"행동유도 1~2문장","hashtags":["태그1","태그2","태그3","태그4","태그5"],"youtube_title":"제목 30자 이내","description":"설명란\\n\\n파트너스 링크: ${link}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."}`
    : `${base}\n반드시 아래 JSON으로만 응답:\n{"wow_selected":"선택한 WOW","opening":"호기심 오프닝 20자 이내 ?로 끝","proof":"증명 2~3문장 수치/스펙/비교","usage":"활용 2~3문장 구체적 장면","cta":"행동유도 1~2문장","hashtags":["태그1","태그2","태그3","태그4","태그5"],"youtube_title":"제목 30자 이내","description":"설명란\\n\\n파트너스 링크: ${link}\\n\\n※ 이 영상은 쿠팡파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다."}`;

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type':'application/json','x-api-key':claudeKey,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true' },
      body: JSON.stringify({ model:'claude-sonnet-4-20250514', max_tokens:1500, messages:[{role:'user',content:prompt}] })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    const text = data.content[0].text.replace(/```json/gi,'').replace(/```/g,'').trim();
    const script = JSON.parse(text.match(/\{[\s\S]*\}/)[0]);
    script.product=analysis.product_name; script.category=category;
    script.coupangLink=coupangLink; script.type=isPain?'pain':'wow';
    script.analysis=analysis; script.createdAt=new Date().toISOString();
    return script;
  } catch(e) { showError('스크립트 생성 실패: '+e.message); return null; }
}

// =============================================
// 히스토리 / UI 유틸
// =============================================
function saveToHistory(script) {
  const h = JSON.parse(localStorage.getItem('script_history')||'[]');
  h.unshift(script);
  localStorage.setItem('script_history', JSON.stringify(h.slice(0,100)));
}
function loadHistory() { return JSON.parse(localStorage.getItem('script_history')||'[]'); }
function showError(msg) {
  const el = document.getElementById('notification');
  if (!el) return;
  el.textContent='❌ '+msg; el.className='notification error show';
  setTimeout(()=>el.classList.remove('show'),4000);
}
function showSuccess(msg) {
  const el = document.getElementById('notification');
  if (!el) return;
  el.textContent='✅ '+msg; el.className='notification success show';
  setTimeout(()=>el.classList.remove('show'),3000);
}
function copyToClipboard(text) { navigator.clipboard.writeText(text); showSuccess('복사됐습니다'); }
