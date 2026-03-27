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

print("=== 니치 쇼츠 자동 렌더링 v3.1 ===")
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
        size = Path(path).stat().st_size if Path(path).exists() else 0
        return size > 1000
    except Exception as e:
        print(f"  다운로드 실패: {e}")
        return False

def get_video_duration(path):
    """영상 길이 조회"""
    try:
        r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', str(path)])
        return float(r.stdout.strip() or '0')
    except:
        return 0

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
# 1단계: TTS (타임포인트 기반)
# =============================================
def generate_tts():
    print("\n[1/6] TTS 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    if is_wow:
        raw = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('proof',''),
               SCRIPT_DATA.get('usage',''), SCRIPT_DATA.get('cta','')]
    else:
        raw = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('empathy',''),
               SCRIPT_DATA.get('solution',''), SCRIPT_DATA.get('cta','')]

    sentences = [convert_units(s.strip()) for s in raw if s.strip()]
    cat_key   = SCRIPT_DATA.get('category', {}).get('key', 'gadget')
    voice_map = {
        'pet':('ko-KR-Wavenet-A','FEMALE'), 'single':('ko-KR-Wavenet-D','MALE'),
        'sleep':('ko-KR-Wavenet-A','FEMALE'), 'homeoffice':('ko-KR-Wavenet-D','MALE'),
        'kitchen':('ko-KR-Wavenet-B','FEMALE'), 'gadget':('ko-KR-Wavenet-C','MALE'),
    }
    vname, vgender = voice_map.get(cat_key, ('ko-KR-Wavenet-C','MALE'))

    # 단어 단위 마크 삽입 (자막 싱크용)
    word_marks = []
    ssml_parts = ['<speak>']
    mark_idx = 0
    for sent_idx, sent in enumerate(sentences):
        words = sent.split()
        for w_idx, word in enumerate(words):
            mark_name = f"w{mark_idx}"
            ssml_parts.append(f'<mark name="{mark_name}"/>{word} ')
            word_marks.append({'mark': mark_name, 'word': word, 'sent_idx': sent_idx, 'w_idx': w_idx})
            mark_idx += 1
    ssml_parts.append('</speak>')
    ssml = ''.join(ssml_parts)

    try:
        res = requests.post(
            f'https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={GCLOUD_KEY}',
            json={
                'input': {'ssml': ssml},
                'voice': {'languageCode': 'ko-KR', 'name': vname, 'ssmlGender': vgender},
                'audioConfig': {'audioEncoding': 'MP3', 'speakingRate': 1.1, 'pitch': 1.5},
                'enableTimePointing': ['SSML_MARK']
            },
            timeout=30
        )
        data = res.json()
        if 'audioContent' not in data:
            raise Exception(str(data))

        with open('temp/audio.mp3', 'wb') as f:
            f.write(base64.b64decode(data['audioContent']))

        # 타임포인트 매핑
        tp_map = {}
        for tp in data.get('timepoints', []):
            tp_map[tp['markName']] = tp['timeSeconds']

        # 단어별 시작 시간 구성
        word_timings = []
        for i, wm in enumerate(word_marks):
            start = tp_map.get(wm['mark'], None)
            if start is None:
                continue
            # 끝 시간 = 다음 단어 시작 또는 +0.4초
            if i + 1 < len(word_marks) and word_marks[i+1]['mark'] in tp_map:
                end = tp_map[word_marks[i+1]['mark']]
            else:
                end = start + 0.4
            word_timings.append({
                'word': wm['word'], 'start': start, 'end': end,
                'sent_idx': wm['sent_idx'], 'w_idx': wm['w_idx']
            })

        # 문장별 시간 범위도 계산
        sent_timings = {}
        for wt in word_timings:
            si = wt['sent_idx']
            if si not in sent_timings:
                sent_timings[si] = {'start': wt['start'], 'end': wt['end']}
            else:
                sent_timings[si]['end'] = wt['end']

        dur_r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'])
        duration = float(dur_r.stdout.strip() or '28')

        print(f"  TTS 완료: {duration:.1f}초, 단어 {len(word_timings)}개 타임포인트")
        return sentences, duration, word_timings, sent_timings

    except Exception as e:
        print(f"  TTS 실패: {e}")
        run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '28', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        n = len(sentences)
        wt = []
        st = {}
        for i, sent in enumerate(sentences):
            s = i * 28 / n
            e = (i+1) * 28 / n
            st[i] = {'start': s, 'end': e}
            words = sent.split()
            for j, w in enumerate(words):
                ws = s + j * (e-s) / max(len(words),1)
                we = s + (j+1) * (e-s) / max(len(words),1)
                wt.append({'word':w,'start':ws,'end':we,'sent_idx':i,'w_idx':j})
        return sentences, 28.0, wt, st

# =============================================
# 2단계: 쿠팡 소스 다운로드 및 분류
# =============================================
def prepare_product_sources():
    print("\n[2/6] 제품 소스 준비 중...")

    coupang_videos = SOURCES_DATA.get('_coupang_videos', [])
    coupang_images = SOURCES_DATA.get('_coupang_images', [])

    # 영상 다운로드
    product_videos = []
    for i, v in enumerate(coupang_videos[:5]):
        url = v.get('url', '')
        if not url: continue
        path = f'temp/prod_video_{i}.mp4'
        print(f"  제품 영상 {i+1} 다운로드 중...")
        if download_file(url, path, timeout=60):
            dur = get_video_duration(path)
            if dur > 0.5:
                product_videos.append({'path': path, 'duration': dur})
                print(f"  ✅ 제품 영상 {i+1}: {dur:.1f}초")
            else:
                print(f"  ⚠️ 영상 {i+1} 너무 짧음")

    # 이미지 다운로드
    product_images = []
    for i, img in enumerate(coupang_images[:15]):
        url = img.get('url', '') or img.get('thumb', '')
        if not url: continue
        path = f'temp/prod_img_{i}.jpg'
        if download_file(url, path, timeout=15):
            product_images.append({'path': path})

    print(f"  제품 영상: {len(product_videos)}개, 이미지: {len(product_images)}개")
    return product_videos, product_images

# =============================================
# 3단계: Claude 이미지 분류
# =============================================
def classify_images(image_paths, product_name):
    if not CLAUDE_KEY or not image_paths:
        return {'opening':[], 'proof':[], 'solution':[], 'cta':[]}

    print(f"\n[3/6] Claude 이미지 분류 중... ({len(image_paths)}개)")

    urls_sample = [p['path'] for p in image_paths[:12]]
    url_list = '\n'.join([f"{i}: {p}" for i, p in enumerate(urls_sample)])

    prompt = f"""쇼츠 영상 편집 전문가입니다.
상품명: {product_name}
이미지 파일 경로 목록:
{url_list}

파일명/순서로 이미지 용도를 추론해서 분류하세요.
- opening: 첫 인상, 메인 제품샷
- proof: 스펙/수치/인포그래픽/비교
- solution: 사용 장면, 라이프스타일
- cta: 전체샷, 패키지, 흰 배경

반드시 아래 JSON으로만 응답:
{{"classifications":[{{"index":0,"type":"opening"}},{{"index":1,"type":"proof"}}]}}"""

    try:
        res = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key':CLAUDE_KEY,'anthropic-version':'2023-06-01','content-type':'application/json'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':600,
                  'messages':[{'role':'user','content':prompt}]},
            timeout=20
        )
        text = res.json()['content'][0]['text'].replace('```json','').replace('```','').strip()
        result = json.loads(re.search(r'\{[\s\S]*\}', text).group(0))
        classified = {'opening':[],'proof':[],'solution':[],'cta':[]}
        for item in result.get('classifications',[]):
            idx = item.get('index',-1)
            typ = item.get('type','solution')
            if 0 <= idx < len(image_paths) and typ in classified:
                classified[typ].append(image_paths[idx])
        # 분류 안 된 이미지는 solution에
        classified_indices = {item['index'] for item in result.get('classifications',[])}
        for i, img in enumerate(image_paths[:12]):
            if i not in classified_indices:
                classified['solution'].append(img)
        print(f"  분류: {{{', '.join([f'{k}:{len(v)}' for k,v in classified.items()])}}}")
        return classified
    except Exception as e:
        print(f"  분류 실패: {e} — 균등 분배")
        n = len(image_paths)
        q = max(1, n//4)
        return {
            'opening':  image_paths[:q],
            'proof':    image_paths[q:q*2],
            'solution': image_paths[q*2:q*3],
            'cta':      image_paths[q*3:],
        }

# =============================================
# 4단계: 구간 설계 + 소스 배정
# =============================================
def design_sections_and_assign(sentences, duration, sent_timings, product_videos, product_images_classified):
    print("\n[4/6] 구간 설계 + 소스 배정 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    # 총 제품 영상 길이
    total_video_dur = sum(v['duration'] for v in product_videos)
    has_long_video  = total_video_dur >= 15  # 15초 이상이면 영상 중심

    print(f"  제품 영상 총 {total_video_dur:.1f}초 — {'영상 중심 모드' if has_long_video else '이미지 중심 모드'}")

    # 구간 정의 (sent_idx: 어느 문장에 해당하는지)
    if is_wow:
        section_defs = [
            ('opening_1','opening',0,0), ('opening_2','opening',0,1),
            ('proof_1','proof',1,0),     ('proof_2','proof',1,1),   ('proof_3','proof',1,2),
            ('usage_1','solution',2,0),  ('usage_2','solution',2,1),('usage_3','solution',2,2),
            ('cta_1','cta',3,0),         ('cta_2','cta',3,1),
        ]
    else:
        section_defs = [
            ('opening_1','opening',0,0), ('opening_2','opening',0,1),
            ('empathy_1','empathy',1,0), ('empathy_2','empathy',1,1),('empathy_3','empathy',1,2),
            ('solution_1','solution',2,0),('solution_2','solution',2,1),('solution_3','solution',2,2),
            ('cta_1','cta',3,0),         ('cta_2','cta',3,1),
        ]

    n_sent = len(sentences)
    # 문장별 시간
    def seg_time(sent_idx, subcut, n_subcuts):
        ti = sent_timings.get(sent_idx, {'start': sent_idx*duration/n_sent, 'end': (sent_idx+1)*duration/n_sent})
        seg_dur = (ti['end'] - ti['start']) / n_subcuts
        start   = ti['start'] + subcut * seg_dur
        end     = ti['start'] + (subcut+1) * seg_dur
        return start, end, max(seg_dur, 0.5)

    # 구간별 최대 서브컷 수 파악
    subcut_counts = {}
    for (key, img_type, sent_idx, subcut) in section_defs:
        k = (img_type, sent_idx)
        subcut_counts[k] = max(subcut_counts.get(k, 0), subcut + 1)

    # 소스 인덱스 트래커
    img_idx    = {t: 0 for t in ['opening','proof','solution','empathy','cta']}
    vid_idx    = 0
    vid_seek   = 0.0  # 현재 영상에서 몇 초부터 사용할지

    # Gemini 프롬프트 (보조용)
    main_pain = (SCRIPT_DATA.get('analysis', {}).get('main_pains') or [''])[0]
    gemini_prompts = {
        'opening': f'Korean person extremely frustrated, dramatic dark lighting, close-up face, vertical 9:16',
        'empathy': f'Person struggling with problem "{main_pain}", dark moody realistic, vertical 9:16',
        'cta':     f'Person smiling satisfied, bright warm lifestyle, vertical 9:16',
    }

    sections = []
    for (key, img_type, sent_idx, subcut) in section_defs:
        if sent_idx >= n_sent:
            continue
        n_subcuts = subcut_counts.get((img_type, sent_idx), 1)
        start, end, dur = seg_time(sent_idx, subcut, n_subcuts)

        src = None  # {'type': 'video'/'image'/'ai'/'color', ...}

        # ── 영상 중심 모드: 제품 영상을 구간별로 seek해서 사용 ──
        if has_long_video and img_type in ['proof','solution','usage']:
            if vid_idx < len(product_videos):
                vid = product_videos[vid_idx]
                remaining = vid['duration'] - vid_seek
                if remaining >= dur:
                    src = {'type':'video','path':vid['path'],'seek':vid_seek,'dur':dur}
                    vid_seek += dur
                    if vid_seek >= vid['duration'] - 0.5:
                        vid_idx += 1
                        vid_seek = 0.0
                elif remaining > 0.5:
                    src = {'type':'video','path':vid['path'],'seek':vid_seek,'dur':remaining}
                    vid_idx += 1
                    vid_seek = 0.0
                else:
                    vid_idx += 1
                    vid_seek = 0.0

        # ── 이미지 배정 (영상 없거나 opening/cta) ──
        if src is None:
            img_list = product_images_classified.get(img_type, [])
            # empathy는 solution 이미지 활용
            if not img_list and img_type == 'empathy':
                img_list = product_images_classified.get('solution', [])
            # 이미지가 있으면 순환 사용 (블랙 화면 방지)
            if img_list:
                idx = img_idx.get(img_type, 0) % len(img_list)
                src = {'type':'image','path':img_list[idx]['path']}
                img_idx[img_type] = img_idx.get(img_type, 0) + 1
            elif img_type in gemini_prompts:
                src = {'type':'ai','prompt':gemini_prompts[img_type]}
            else:
                # 다른 타입 이미지 순환 (블랙 화면 방지)
                all_imgs = []
                for imgs in product_images_classified.values():
                    all_imgs.extend(imgs)
                if all_imgs:
                    fallback_idx = sum(img_idx.values()) % len(all_imgs)
                    src = {'type':'image','path':all_imgs[fallback_idx]['path']}
                else:
                    src = {'type':'ai','prompt':f'{SCRIPT_DATA.get("product","")} product lifestyle, vertical 9:16'}

        sections.append({
            'key': key, 'img_type': img_type,
            'sent_idx': sent_idx, 'subcut': subcut,
            'start': start, 'end': end, 'duration': dur,
            'text': sentences[sent_idx],
            'src': src,
        })
        src_desc = f"{src['type']}:{src.get('path','')[-20:] if src.get('path') else src.get('prompt','')[:30]}"
        print(f"  [{key}] {dur:.1f}초 → {src_desc}")

    return sections

# =============================================
# 5단계: 클립 생성
# =============================================
gemini_cache = {}

def get_ai_image(prompt):
    if prompt in gemini_cache:
        return gemini_cache[prompt]
    if not GEMINI_KEY:
        return None
    try:
        res = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={GEMINI_KEY}',
            json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseModalities':['TEXT','IMAGE']}},
            timeout=40
        )
        parts = res.json().get('candidates',[{}])[0].get('content',{}).get('parts',[])
        img_part = next((p for p in parts if 'inlineData' in p), None)
        if img_part:
            path = f'temp/ai_{len(gemini_cache):02d}.jpg'
            with open(path,'wb') as f:
                f.write(base64.b64decode(img_part['inlineData']['data']))
            gemini_cache[prompt] = path
            return path
    except Exception as e:
        print(f"  Gemini 실패: {e}")
    gemini_cache[prompt] = None
    return None

def make_clip(sec, out_path):
    src = sec['src']
    dur = sec['duration']
    dur = max(dur, 0.5)
    scale = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
    frames = int(dur * 30)

    if src['type'] == 'video' and Path(src.get('path','')).exists():
        seek = src.get('seek', 0)
        run(['ffmpeg', '-ss', str(seek), '-i', src['path'],
             '-vf', scale, '-t', str(dur), '-r', '30',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
             out_path, '-y'])

    elif src['type'] == 'image' and Path(src.get('path','')).exists():
        is_open = sec['img_type'] == 'opening' and sec['subcut'] == 0
        if is_open:
            zoom = f'zoompan=z=\'if(eq(on,1),1.3,max(zoom-0.003,1.0))\':d={frames}:s={W}x{H}:fps=30'
        else:
            zoom = f'zoompan=z=\'min(zoom+0.0005,1.12)\':d={frames}:s={W}x{H}:fps=30'
        run(['ffmpeg', '-loop', '1', '-i', src['path'],
             '-vf', f'scale={W*2}:{H*2},{zoom}',
             '-t', str(dur), '-r', '30',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
             out_path, '-y'])
        if not Path(out_path).exists():
            run(['ffmpeg', '-loop', '1', '-i', src['path'],
                 '-vf', scale, '-t', str(dur), '-r', '30',
                 '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
                 out_path, '-y'])

    elif src['type'] == 'ai':
        img_path = get_ai_image(src.get('prompt',''))
        if img_path and Path(img_path).exists():
            run(['ffmpeg', '-loop', '1', '-i', img_path,
                 '-vf', scale, '-t', str(dur), '-r', '30',
                 '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
                 out_path, '-y'])

    # 최후 폴백 — 그래도 없으면 직전 클립 복사 or 검정
    if not Path(out_path).exists():
        run(['ffmpeg', '-f', 'lavfi', '-i', f'color=black:size={W}x{H}:rate=30',
             '-t', str(dur), '-c:v', 'libx264', '-preset', 'fast', '-an',
             out_path, '-y'])

def build_clips(sections):
    print("\n[5/6] 클립 생성 중...")
    clips = []
    last_valid = None  # 블랙 화면 방지: 마지막 유효 클립 경로

    for idx, sec in enumerate(sections):
        out = f'temp/clip_{idx:02d}.mp4'
        make_clip(sec, out)

        if Path(out).exists() and Path(out).stat().st_size > 1000:
            last_valid = out
            clips.append({'path': out, 'section': sec})
            print(f"  [{sec['key']}] {sec['duration']:.1f}초 ✅ ({sec['src']['type']})")
        elif last_valid:
            # 블랙 화면 대신 직전 유효 클립 재사용
            import shutil
            shutil.copy(last_valid, out)
            clips.append({'path': out, 'section': sec})
            print(f"  [{sec['key']}] {sec['duration']:.1f}초 ♻️ (직전 클립 재사용)")
        else:
            # 첫 클립부터 실패 — 검정 배경
            run(['ffmpeg', '-f', 'lavfi', '-i', f'color=black:size={W}x{H}:rate=30',
                 '-t', str(sec['duration']), '-c:v', 'libx264', '-preset', 'fast', '-an', out, '-y'])
            clips.append({'path': out, 'section': sec})

    return clips

# =============================================
# 6단계: ASS 자막 (단어 단위 싱크 + 밈 스타일)
# =============================================
def build_subtitles_ass(word_timings, total_duration):
    print("\n[6/6] 자막 생성 중 (단어 싱크 + 밈 스타일)...")

    def fmt(t):
        t = max(0, t)
        return f"{int(t//3600)}:{int((t%3600)//60):02d}:{int(t%60):02d}.{int((t%1)*100):02d}"

    # 밈 스타일 색상 교대 (노란/흰/하늘)
    COLORS = ['&H00FFE500', '&H00FFFFFF', '&H00E5FF00']

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Hook,Noto Sans CJK KR,140,&H00FFE500,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,6,0,1,12,7,5,40,40,960,1
Style: W0,Noto Sans CJK KR,95,&H00FFE500,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,8,5,5,40,40,960,1
Style: W1,Noto Sans CJK KR,95,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,8,5,5,40,40,960,1
Style: W2,Noto Sans CJK KR,95,&H0000FFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,8,5,5,40,40,960,1
Style: Spec,Noto Sans CJK KR,68,&H0000E5FF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,6,3,2,40,40,820,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    color_idx = 0
    prev_sent = -1

    # 단어별 자막 생성
    for i, wt in enumerate(word_timings):
        word  = wt['word'].strip()
        if not word:
            continue

        start = wt['start']
        end   = wt['end']
        sent_i = wt['sent_idx']

        # 첫 문장 첫 단어: 대형 후킹 스타일
        if sent_i == 0 and wt['w_idx'] == 0:
            ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},Hook,,0,0,0,,{word}\n"
        else:
            # 밈 스타일: 단어마다 색상 교대
            style = f"W{color_idx % 3}"
            ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},{style},,0,0,0,,{word}\n"

        if sent_i != prev_sent:
            color_idx = 0
            prev_sent = sent_i
        else:
            color_idx += 1

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)
    print(f"  자막 {len(word_timings)}개 단어 완료")
    return path

# =============================================
# 7단계: 최종 합성
# =============================================
def final_render(clips, ass_path):
    print("\n[7/6] 최종 합성 중...")

    with open('temp/concat.txt', 'w') as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c['path'])}'\n")

    run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'temp/concat.txt',
         '-c', 'copy', 'temp/merged.mp4', '-y'])

    if not Path('temp/merged.mp4').exists():
        raise Exception("클립 연결 실패")

    abs_ass = os.path.abspath(ass_path).replace('\\','/').replace(':','\\:')

    run(['ffmpeg',
         '-i', 'temp/merged.mp4', '-i', 'temp/audio.mp3',
         '-vf', f"ass='{abs_ass}'",
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
         '-c:a', 'aac', '-b:a', '128k',
         '-shortest', 'output/final.mp4', '-y'])

    if not Path('output/final.mp4').exists():
        print("  자막 실패 — 자막 없이 재시도")
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

        # TTS
        sentences, duration, word_timings, sent_timings = generate_tts()

        # 제품 소스 준비
        product_videos, product_images = prepare_product_sources()

        # 이미지 분류 (영상이 부족할 때 사용)
        product_name = SCRIPT_DATA.get('product', '')
        classified = classify_images(product_images, product_name) if product_images else {'opening':[],'proof':[],'solution':[],'cta':[]}

        # 구간 설계 + 소스 배정
        sections = design_sections_and_assign(
            sentences, duration, sent_timings,
            product_videos, classified
        )

        # 클립 생성
        clips = build_clips(sections)

        # 자막 (단어 단위 싱크)
        ass_path = build_subtitles_ass(word_timings, duration)

        # 최종 합성
        final_render(clips, ass_path)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback; traceback.print_exc()
        exit(1)
