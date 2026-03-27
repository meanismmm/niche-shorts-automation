import os
import json
import requests
import subprocess
import base64
import re
from pathlib import Path

# =============================================
# 환경변수
# =============================================
SCRIPT_DATA  = json.loads(os.environ.get('SCRIPT_DATA', '{}'))
SOURCES_DATA = json.loads(os.environ.get('SOURCES_DATA', '{}'))
GEMINI_KEY   = os.environ.get('GEMINI_API_KEY', '')
GCLOUD_KEY   = os.environ.get('GOOGLE_CLOUD_KEY', '')
CLAUDE_KEY   = os.environ.get('CLAUDE_API_KEY', '')

Path('output').mkdir(exist_ok=True)
Path('temp').mkdir(exist_ok=True)

W, H = 1080, 1920
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

print("=== 니치 쇼츠 자동 렌더링 v3.0 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

# =============================================
# 유틸
# =============================================
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  CMD 오류: {r.stderr[-300:]}")
    return r

def convert_units(text):
    text = re.sub(r'(\d+\.?\d*)\s*L\b',  r'\1리터',     text)
    text = re.sub(r'(\d+\.?\d*)\s*ml\b', r'\1밀리리터', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+\.?\d*)\s*kg\b', r'\1킬로그램', text)
    text = re.sub(r'(\d+\.?\d*)\s*g\b',  r'\1그램',     text)
    text = re.sub(r'(\d+\.?\d*)\s*cm\b', r'\1센티미터', text)
    text = re.sub(r'(\d+\.?\d*)\s*%',    r'\1퍼센트',   text)
    return text

def download_file(url, path, timeout=30):
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.coupang.com/'}
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return Path(path).exists() and Path(path).stat().st_size > 500
    except Exception as e:
        print(f"  다운로드 실패: {e}")
        return False

def esc(text):
    """FFmpeg drawtext 이스케이프"""
    for ch in ["'", ':', '\\', '[', ']']:
        text = text.replace(ch, '')
    return text

# =============================================
# 0단계: 폰트 설치
# =============================================
def install_fonts():
    print("\n[0/6] 폰트 설치 중...")
    run(['sudo', 'apt-get', 'update', '-qq'])
    run(['sudo', 'apt-get', 'install', '-y', '--fix-missing', 'fonts-noto-cjk'])
    run(['fc-cache', '-fv'])
    print("  완료")

# =============================================
# 1단계: TTS
# =============================================
def generate_tts():
    print("\n[1/6] TTS 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    if is_wow:
        raw_sents = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('proof',''), SCRIPT_DATA.get('usage',''), SCRIPT_DATA.get('cta','')]
    else:
        raw_sents = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('empathy',''), SCRIPT_DATA.get('solution',''), SCRIPT_DATA.get('cta','')]

    sentences = [convert_units(s.strip()) for s in raw_sents if s.strip()]
    cat_key   = SCRIPT_DATA.get('category', {}).get('key', 'gadget')
    voice_map = {
        'pet':('ko-KR-Wavenet-A','FEMALE'), 'single':('ko-KR-Wavenet-D','MALE'),
        'sleep':('ko-KR-Wavenet-A','FEMALE'), 'homeoffice':('ko-KR-Wavenet-D','MALE'),
        'kitchen':('ko-KR-Wavenet-B','FEMALE'), 'gadget':('ko-KR-Wavenet-C','MALE'),
    }
    vname, vgender = voice_map.get(cat_key, ('ko-KR-Wavenet-C','MALE'))
    ssml = '<speak>' + ''.join(f'<mark name="s{i}"/>{s}' for i,s in enumerate(sentences)) + '</speak>'

    try:
        res = requests.post(
            f'https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={GCLOUD_KEY}',
            json={'input':{'ssml':ssml},'voice':{'languageCode':'ko-KR','name':vname,'ssmlGender':vgender},
                  'audioConfig':{'audioEncoding':'MP3','speakingRate':1.1,'pitch':1.5},
                  'enableTimePointing':['SSML_MARK']},
            timeout=30
        )
        data = res.json()
        if 'audioContent' not in data:
            raise Exception(str(data))
        with open('temp/audio.mp3','wb') as f:
            f.write(base64.b64decode(data['audioContent']))

        timepoints = {}
        for tp in data.get('timepoints',[]):
            m = tp.get('markName','')
            if m.startswith('s'):
                timepoints[int(m[1:])] = tp.get('timeSeconds',0)

        dur = float(run(['ffprobe','-v','error','-show_entries','format=duration',
                         '-of','default=noprint_wrappers=1:nokey=1','temp/audio.mp3']).stdout.strip() or '28')
        print(f"  TTS 완료: {dur:.1f}초")
        return sentences, dur, timepoints
    except Exception as e:
        print(f"  TTS 실패: {e}")
        run(['ffmpeg','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t','28',
             '-q:a','9','-acodec','libmp3lame','temp/audio.mp3','-y'])
        n = len(sentences)
        return sentences, 28.0, {i: i*(28/max(n,1)) for i in range(n)}

# =============================================
# 2단계: 쿠팡 이미지 Claude 자동 분류
# =============================================
def classify_images_with_claude(image_urls, product_name):
    """Claude가 이미지 URL을 보고 구간별 용도를 자동 분류"""
    if not CLAUDE_KEY or not image_urls:
        return {}

    print(f"\n[2/6] Claude로 이미지 {len(image_urls)}개 자동 분류 중...")

    # URL 목록 (최대 20개)
    urls_to_classify = image_urls[:20]
    url_list = '\n'.join([f"{i}: {url}" for i, url in enumerate(urls_to_classify)])

    prompt = f"""당신은 쇼츠 영상 편집 전문가입니다.

상품명: {product_name}
쿠팡 상세페이지에서 추출한 이미지 URL 목록:
{url_list}

각 이미지 URL을 보고 이미지 용도를 추론해서 아래 구간 중 하나로 분류해주세요.

구간 종류:
- opening: 오프닝용 (강렬한 첫 인상, 메인 제품샷, 감성 장면)
- proof: 증명용 (스펙 인포그래픽, 수치/비교표, 기능 설명)
- solution: 해결/사용 장면 (실제 사용 모습, 라이프스타일)
- cta: CTA용 (제품 전체샷, 패키지, 흰 배경 메인샷)
- skip: 불필요 (배너, 아이콘, 로고, 브랜드 이미지)

분류 기준:
- coupangcdn URL에 /thumbnails/ 포함: opening 또는 cta
- 인포그래픽처럼 보이는 URL (info, spec, feature 등): proof
- 사람이 사용하는 장면 추정: solution
- 작은 아이콘이나 뱃지: skip

반드시 아래 JSON 형식으로만 응답하세요 (JSON 외 텍스트 금지):
{{
  "classifications": [
    {{"index": 0, "type": "opening", "reason": "메인 제품샷"}},
    {{"index": 1, "type": "proof", "reason": "스펙 인포그래픽"}},
    ...
  ]
}}"""

    try:
        res = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': CLAUDE_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1000,
                  'messages': [{'role': 'user', 'content': prompt}]},
            timeout=30
        )
        data = res.json()
        text = data['content'][0]['text'].replace('```json','').replace('```','').strip()
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            raise Exception('JSON 없음')
        result = json.loads(match.group(0))

        classified = {}
        for item in result.get('classifications', []):
            idx  = item.get('index', -1)
            typ  = item.get('type', 'skip')
            if 0 <= idx < len(urls_to_classify) and typ != 'skip':
                if typ not in classified:
                    classified[typ] = []
                classified[typ].append(urls_to_classify[idx])

        print(f"  분류 결과: {{{', '.join([f'{k}: {len(v)}개' for k,v in classified.items()])}}}")
        return classified

    except Exception as e:
        print(f"  분류 실패: {e} — 순서대로 배치")
        # 폴백: 순서대로 배치
        n = len(urls_to_classify)
        return {
            'opening':  urls_to_classify[:max(1, n//5)],
            'proof':    urls_to_classify[max(1,n//5):max(2,n//5*2)],
            'solution': urls_to_classify[max(2,n//5*2):max(3,n//5*3)],
            'cta':      urls_to_classify[max(3,n//5*3):],
        }

# =============================================
# 3단계: 구간별 소스 배치 (10구간)
# =============================================
def assign_sources(sentences, total_duration, timepoints, classified_images):
    print("\n[3/6] 구간별 소스 배치 중...")
    is_wow   = SCRIPT_DATA.get('type') == 'wow'
    product  = SCRIPT_DATA.get('product', '')
    analysis = SCRIPT_DATA.get('analysis', {})
    main_pain = (analysis.get('main_pains') or [''])[0]

    # 구간 정의
    if is_wow:
        section_defs = [
            ('opening_1', 'opening', 0, 0),
            ('opening_2', 'opening', 0, 1),
            ('proof_1',   'proof',   1, 0),
            ('proof_2',   'proof',   1, 1),
            ('proof_3',   'proof',   1, 2),
            ('usage_1',   'solution',2, 0),
            ('usage_2',   'solution',2, 1),
            ('usage_3',   'solution',2, 2),
            ('cta_1',     'cta',     3, 0),
            ('cta_2',     'cta',     3, 1),
        ]
    else:
        section_defs = [
            ('opening_1',  'opening',  0, 0),
            ('opening_2',  'opening',  0, 1),
            ('empathy_1',  'empathy',  1, 0),
            ('empathy_2',  'empathy',  1, 1),
            ('empathy_3',  'empathy',  1, 2),
            ('solution_1', 'solution', 2, 0),
            ('solution_2', 'solution', 2, 1),
            ('solution_3', 'solution', 2, 2),
            ('cta_1',      'cta',      3, 0),
            ('cta_2',      'cta',      3, 1),
        ]

    # 문장별 시간 범위
    n = len(sentences)
    seg_times = []
    for i in range(n):
        s = timepoints.get(i, i * total_duration / n)
        e = timepoints.get(i+1, s + total_duration / n) if i+1 < n else total_duration
        seg_times.append((s, e))

    # 이미지 인덱스 트래커
    img_idx = {k: 0 for k in ['opening','proof','solution','empathy','cta']}

    # Gemini 프롬프트 (제품 소스가 없을 때 보조)
    gemini_prompts = {
        'opening':  f'Korean person extremely frustrated, dramatic dark lighting, close-up emotional face, no product, vertical 9:16 portrait',
        'empathy':  f'Person struggling with problem "{main_pain}", realistic dark moody, vertical 9:16',
        'cta':      f'Person smiling satisfied, bright warm lifestyle, vertical 9:16',
    }

    sections = []
    for (key, img_type, sent_idx, subcut) in section_defs:
        if sent_idx >= len(seg_times):
            continue

        seg_start, seg_end = seg_times[sent_idx]
        seg_dur   = seg_end - seg_start
        n_subcuts = 1 if seg_dur < 3 else (2 if seg_dur < 6 else 3)
        cut_dur   = seg_dur / n_subcuts

        start = seg_start + subcut * cut_dur
        end   = seg_start + (subcut+1) * cut_dur
        dur   = cut_dur

        # 이미지 배정
        img_url = None
        img_urls_for_type = classified_images.get(img_type, [])

        # opening은 감성 우선 (Gemini), 나머지는 제품 이미지 우선
        if img_type in ['solution','proof','cta'] and img_urls_for_type:
            idx = img_idx[img_type] % len(img_urls_for_type)
            img_url = img_urls_for_type[idx]
            img_idx[img_type] += 1
        elif img_type == 'opening' and img_urls_for_type and subcut > 0:
            # 오프닝 2번째 컷은 제품 이미지
            idx = img_idx[img_type] % len(img_urls_for_type)
            img_url = img_urls_for_type[idx]
            img_idx[img_type] += 1
        elif img_type == 'empathy' and img_urls_for_type:
            idx = img_idx.get('empathy',0) % len(img_urls_for_type)
            img_url = img_urls_for_type[idx]
            img_idx['empathy'] = img_idx.get('empathy',0) + 1

        # 웹앱에서 선택된 소스 있으면 덮어쓰기
        selected = SOURCES_DATA.get(key, {}).get('selected', {})
        if selected and selected.get('data', {}).get('url'):
            img_url = selected['data']['url']

        sections.append({
            'key':       key,
            'img_type':  img_type,
            'sent_idx':  sent_idx,
            'subcut':    subcut,
            'start':     start,
            'end':       end,
            'duration':  max(dur, 0.5),
            'text':      sentences[sent_idx] if sent_idx < len(sentences) else '',
            'img_url':   img_url,
            'gemini_prompt': gemini_prompts.get(img_type) if not img_url else None,
        })
        print(f"  [{key}] {img_type} {dur:.1f}초 — {'제품이미지' if img_url else 'Gemini AI'}")

    return sections

# =============================================
# 4단계: 클립 생성 (이미지 다운로드 + FFmpeg)
# =============================================
def download_or_generate_image(section, idx):
    """이미지 URL 다운로드 또는 Gemini AI 생성"""
    img_url = section.get('img_url')
    out_path = f'temp/src_{idx:02d}.jpg'

    # 1. URL 다운로드
    if img_url:
        if download_file(img_url, out_path):
            return out_path, 'image'

    # 2. Gemini AI 생성
    prompt = section.get('gemini_prompt')
    if prompt and GEMINI_KEY:
        try:
            res = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={GEMINI_KEY}',
                json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseModalities':['TEXT','IMAGE']}},
                timeout=40
            )
            parts = res.json().get('candidates',[{}])[0].get('content',{}).get('parts',[])
            img_part = next((p for p in parts if 'inlineData' in p), None)
            if img_part:
                with open(out_path, 'wb') as f:
                    f.write(base64.b64decode(img_part['inlineData']['data']))
                return out_path, 'ai'
        except Exception as e:
            print(f"  Gemini 실패: {e}")

    return None, 'color'

def make_clip(src_path, src_type, duration, out_path, is_opening=False):
    """클립 생성 (줌인 효과 포함)"""
    duration = max(duration, 0.5)
    scale    = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
    frames   = int(duration * 30)

    if src_type in ('image','ai') and src_path and Path(src_path).exists():
        if is_opening:
            zoom = f'zoompan=z=\'if(eq(on,1),1.3,max(zoom-0.003,1.0))\':d={frames}:s={W}x{H}:fps=30'
        else:
            zoom = f'zoompan=z=\'min(zoom+0.0005,1.12)\':d={frames}:s={W}x{H}:fps=30'

        run(['ffmpeg', '-loop', '1', '-i', src_path,
             '-vf', f'scale={W*2}:{H*2},{zoom}',
             '-t', str(duration), '-r', '30',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
             out_path, '-y'])

        if not Path(out_path).exists():
            # 줌 실패 시 단순 스케일
            run(['ffmpeg', '-loop', '1', '-i', src_path,
                 '-vf', scale, '-t', str(duration), '-r', '30',
                 '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
                 out_path, '-y'])
    else:
        # 검정 배경
        run(['ffmpeg', '-f', 'lavfi', '-i', f'color=black:size={W}x{H}:rate=30',
             '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-an',
             out_path, '-y'])

def build_clips(sections):
    print("\n[4/6] 클립 생성 중...")
    clips = []
    for idx, sec in enumerate(sections):
        src_path, src_type = download_or_generate_image(sec, idx)
        out = f'temp/clip_{idx:02d}.mp4'
        make_clip(src_path, src_type, sec['duration'], out, is_opening=(idx==0))
        if Path(out).exists():
            clips.append({'path': out, 'section': sec, 'src_type': src_type})
            print(f"  [{sec['key']}] {src_type} {sec['duration']:.1f}초 ✅")
        else:
            # 폴백: 검정 배경
            make_clip(None, 'color', sec['duration'], out)
            if Path(out).exists():
                clips.append({'path': out, 'section': sec, 'src_type': 'color'})
    return clips

# =============================================
# 5단계: FFmpeg 오버레이 텍스트 추출
# =============================================
def extract_overlay_text(section, analysis):
    """구간별 오버레이 텍스트 결정"""
    img_type  = section['img_type']
    text      = section['text']
    subcut    = section['subcut']
    key_specs = analysis.get('key_specs', [])
    price_appeal = analysis.get('price_appeal', '')

    if img_type == 'proof' and key_specs:
        # 스펙 강조 텍스트
        spec_idx = section['subcut'] % len(key_specs)
        return key_specs[spec_idx], 'spec'
    elif img_type == 'cta':
        return price_appeal[:20] if price_appeal else '지금 링크 클릭!', 'cta'
    else:
        return None, None

# =============================================
# 6단계: ASS 자막 생성 (혼합 스타일)
# =============================================
def build_subtitles_ass(clips, total_duration):
    print("\n[5/6] 자막 생성 중 (혼합 스타일)...")

    def fmt(t):
        t = max(0, t)
        return f"{int(t//3600)}:{int((t%3600)//60):02d}:{int(t%60):02d}.{int((t%1)*100):02d}"

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Opening,Noto Sans CJK KR,130,&H00FFE500,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,6,0,1,10,6,5,60,60,960,1
Style: Body,Noto Sans CJK KR,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,3,0,1,7,4,5,60,60,960,1
Style: Spec,Noto Sans CJK KR,65,&H0000E5FF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,6,3,5,60,60,840,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    # 문장별 첫 서브컷에만 자막 표시
    shown_sents = set()
    analysis    = SCRIPT_DATA.get('analysis', {})

    for clip_data in clips:
        sec      = clip_data['section']
        start    = sec['start']
        end      = sec['end']
        text     = sec['text']
        img_type = sec['img_type']
        subcut   = sec['subcut']
        sent_key = (sec['sent_idx'], img_type)

        # ── 오프닝 첫 컷: 핵심 단어 대형 노란색 ──
        if img_type == 'opening' and subcut == 0:
            # 핵심 단어 추출 (첫 어절)
            words = [w for w in re.split(r'[\s,.!?]+', text) if len(w) >= 2]
            kw = words[0][:8] if words else text[:6]
            ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},Opening,,0,0,0,,{kw}\n"

        # ── 본문: 문장 전체 흰색 중앙 ──
        elif sent_key not in shown_sents:
            shown_sents.add(sent_key)
            # 줄바꿈 (16자 기준)
            if len(text) > 16:
                mid  = len(text) // 2
                # 중간 공백 찾기
                left  = text[:mid].rfind(' ')
                right = text[mid:].find(' ')
                if left > mid//2:
                    text_fmt = text[:left] + '\\N' + text[left+1:]
                elif right != -1:
                    pos = mid + right
                    text_fmt = text[:pos] + '\\N' + text[pos+1:]
                else:
                    text_fmt = text[:mid] + '\\N' + text[mid:]
            else:
                text_fmt = text

            ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},Body,,0,0,0,,{text_fmt}\n"

        # ── Spec 오버레이 (증명 구간) ──
        overlay_text, overlay_type = extract_overlay_text(sec, analysis)
        if overlay_text and overlay_type == 'spec':
            spec_text = esc(overlay_text)
            ass += f"Dialogue: 1,{fmt(start)},{fmt(end)},Spec,,0,0,0,,{spec_text}\n"

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)
    print(f"  자막 완료")
    return path

# =============================================
# 7단계: 최종 합성
# =============================================
def final_render(clips, ass_path):
    print("\n[6/6] 최종 합성 중...")

    # 클립 연결
    with open('temp/concat.txt', 'w') as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c['path'])}'\n")

    run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'temp/concat.txt',
         '-c', 'copy', 'temp/merged.mp4', '-y'])

    if not Path('temp/merged.mp4').exists():
        raise Exception("클립 연결 실패")

    abs_ass = os.path.abspath(ass_path).replace('\\','/').replace(':','\\:')

    # 자막 + 음성 합성
    run(['ffmpeg',
         '-i', 'temp/merged.mp4',
         '-i', 'temp/audio.mp3',
         '-vf', f"ass='{abs_ass}'",
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
         '-c:a', 'aac', '-b:a', '128k',
         '-shortest', 'output/final.mp4', '-y'])

    if not Path('output/final.mp4').exists():
        print("  자막 합성 실패 — 자막 없이 재시도")
        run(['ffmpeg',
             '-i', 'temp/merged.mp4', '-i', 'temp/audio.mp3',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
             '-c:a', 'aac', '-b:a', '128k',
             '-shortest', 'output/final.mp4', '-y'])

    if Path('output/final.mp4').exists():
        size = Path('output/final.mp4').stat().st_size / 1024 / 1024
        print(f"\n=== 완료: output/final.mp4 ({size:.1f}MB) ===")
    else:
        raise Exception("최종 영상 생성 실패")

# =============================================
# 메인
# =============================================
if __name__ == '__main__':
    try:
        install_fonts()

        sentences, duration, timepoints = generate_tts()

        # 쿠팡 이미지 분류
        coupang_images = SOURCES_DATA.get('_coupang_images', [])
        image_urls = [img.get('url','') or img.get('thumb','') for img in coupang_images if img.get('url') or img.get('thumb')]

        product = SCRIPT_DATA.get('product', '')
        classified = classify_images_with_claude(image_urls, product) if image_urls else {}

        analysis = SCRIPT_DATA.get('analysis', {})
        sections = assign_sources(sentences, duration, timepoints, classified)
        clips    = build_clips(sections)
        ass_path = build_subtitles_ass(clips, duration)
        final_render(clips, ass_path)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback; traceback.print_exc()
        exit(1)
