import os
import json
import requests
import subprocess
import base64
import re
from pathlib import Path

# =============================================
# 환경변수 로드
# =============================================
SCRIPT_DATA  = json.loads(os.environ.get('SCRIPT_DATA', '{}'))
SOURCES_DATA = json.loads(os.environ.get('SOURCES_DATA', '{}'))
PEXELS_KEY   = os.environ.get('PEXELS_API_KEY', '')
GEMINI_KEY   = os.environ.get('GEMINI_API_KEY', '')
GCLOUD_KEY   = os.environ.get('GOOGLE_CLOUD_KEY', '')
CLAUDE_KEY   = os.environ.get('CLAUDE_API_KEY', '')

Path('output').mkdir(exist_ok=True)
Path('temp').mkdir(exist_ok=True)

W, H = 1080, 1920

print("=== 니치 쇼츠 자동 렌더링 v2.5 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

# =============================================
# 유틸
# =============================================
def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  CMD 오류: {result.stderr[-300:]}")
    return result

def convert_units(text):
    text = re.sub(r'(\d+\.?\d*)\s*L\b',  r'\1리터',     text)
    text = re.sub(r'(\d+\.?\d*)\s*ml\b', r'\1밀리리터', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+\.?\d*)\s*kg\b', r'\1킬로그램', text)
    text = re.sub(r'(\d+\.?\d*)\s*g\b',  r'\1그램',     text)
    text = re.sub(r'(\d+\.?\d*)\s*cm\b', r'\1센티미터', text)
    text = re.sub(r'(\d+\.?\d*)\s*%',    r'\1퍼센트',   text)
    return text

def download_file(url, path, timeout=60):
    """URL에서 파일 다운로드"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.coupang.com/',
        }
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return Path(path).exists() and Path(path).stat().st_size > 1000
    except Exception as e:
        print(f"  다운로드 실패 ({url[:60]}...): {e}")
        return False

# =============================================
# 0단계: 폰트 설치
# =============================================
def install_fonts():
    print("\n[0/6] 한국어 폰트 설치 중...")
    run(['sudo', 'apt-get', 'update', '-qq'])
    run(['sudo', 'apt-get', 'install', '-y', '--fix-missing', 'fonts-noto-cjk'])
    run(['fc-cache', '-fv'])
    print("  폰트 설치 완료")

# =============================================
# 1단계: TTS 음성 생성
# =============================================
def generate_tts():
    print("\n[1/6] TTS 음성 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    if is_wow:
        sentences = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('proof',''), SCRIPT_DATA.get('usage',''), SCRIPT_DATA.get('cta','')]
    else:
        sentences = [SCRIPT_DATA.get('opening',''), SCRIPT_DATA.get('empathy',''), SCRIPT_DATA.get('solution',''), SCRIPT_DATA.get('cta','')]

    sentences = [convert_units(s.strip()) for s in sentences if s.strip()]
    narration = ' '.join(sentences)

    cat_key = SCRIPT_DATA.get('category', {}).get('key', 'gadget')
    voice_map = {
        'pet': ('ko-KR-Wavenet-A','FEMALE'), 'single': ('ko-KR-Wavenet-D','MALE'),
        'sleep': ('ko-KR-Wavenet-A','FEMALE'), 'homeoffice': ('ko-KR-Wavenet-D','MALE'),
        'kitchen': ('ko-KR-Wavenet-B','FEMALE'), 'gadget': ('ko-KR-Wavenet-C','MALE'),
    }
    voice_name, voice_gender = voice_map.get(cat_key, ('ko-KR-Wavenet-C','MALE'))

    ssml = '<speak>' + ''.join(f'<mark name="s{i}"/>{s}' for i, s in enumerate(sentences)) + '</speak>'

    try:
        res = requests.post(
            f'https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={GCLOUD_KEY}',
            json={'input':{'ssml':ssml},'voice':{'languageCode':'ko-KR','name':voice_name,'ssmlGender':voice_gender},'audioConfig':{'audioEncoding':'MP3','speakingRate':1.15,'pitch':1.5},'enableTimePointing':['SSML_MARK']},
            timeout=30
        )
        data = res.json()
        if 'audioContent' not in data:
            raise Exception(f"TTS 오류: {data}")

        with open('temp/audio.mp3','wb') as f:
            f.write(base64.b64decode(data['audioContent']))

        timepoints = {}
        for tp in data.get('timepoints', []):
            m = tp.get('markName','')
            if m.startswith('s'):
                timepoints[int(m[1:])] = tp.get('timeSeconds', 0)

        result = run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1','temp/audio.mp3'])
        duration = float(result.stdout.strip() or '28')
        print(f"  TTS 완료: {duration:.1f}초, 타임포인트: {timepoints}")
        return sentences, narration, duration, timepoints

    except Exception as e:
        print(f"  TTS 실패: {e}")
        run(['ffmpeg','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t','28','-q:a','9','-acodec','libmp3lame','temp/audio.mp3','-y'])
        n = len(sentences)
        return sentences, narration, 28.0, {i: i*(28/max(n,1)) for i in range(n)}

# =============================================
# 2단계: 구간 설계 (10개)
# =============================================
def design_sections(sentences, total_duration, timepoints):
    print("\n[2/6] 구간 설계 중 (10개 빠른 컷)...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    n = len(sentences)

    seg_times = []
    for i in range(n):
        start = timepoints.get(i, i * total_duration / n)
        end   = timepoints.get(i+1, start + total_duration / n) if i+1 < n else total_duration
        seg_times.append((start, end))

    sections = []
    for i, (start, end) in enumerate(seg_times):
        seg_dur = end - start
        n_cuts  = 1 if seg_dur < 3 else (2 if seg_dur < 6 else 3)
        cut_dur = seg_dur / n_cuts

        if i == 0:       sec_type = 'opening'
        elif i == n-1:   sec_type = 'cta'
        elif is_wow:     sec_type = ['proof','usage'][min(i-1,1)]
        else:            sec_type = ['empathy','solution'][min(i-1,1)]

        for j in range(n_cuts):
            sections.append({
                'type': sec_type, 'sentence': i, 'subcut': j,
                'start': start + j*cut_dur, 'end': start + (j+1)*cut_dur,
                'duration': cut_dur, 'text': sentences[i],
            })

    print(f"  총 {len(sections)}개 구간")
    return sections

# =============================================
# 3단계: 실제 제품 소스 우선 수집
# =============================================
def collect_sources(sections):
    print("\n[3/6] 소스 수집 중 (실제 제품 소스 우선)...")

    product  = SCRIPT_DATA.get('product', '')
    analysis = SCRIPT_DATA.get('analysis', {})
    is_wow   = SCRIPT_DATA.get('type') == 'wow'

    # 웹앱에서 전달된 소스 (URL 선택)
    selected_by_key = {}
    for key, val in SOURCES_DATA.items():
        sel = val.get('selected', {})
        if sel and sel.get('data', {}).get('url'):
            selected_by_key[key] = sel['data']['url']

    # 쿠팡 실제 제품 이미지 (웹앱에서 추출해서 전달)
    coupang_images = SOURCES_DATA.get('_coupang_images', [])
    coupang_videos = SOURCES_DATA.get('_coupang_videos', [])

    print(f"  쿠팡 이미지: {len(coupang_images)}개, 영상: {len(coupang_videos)}개")
    print(f"  웹앱 선택 소스: {list(selected_by_key.keys())}")

    # 쿠팡 소스 다운로드
    downloaded_product_imgs = []
    downloaded_product_vids = []

    # 영상 우선
    for i, v in enumerate(coupang_videos[:5]):
        url = v.get('url', '')
        if not url: continue
        path = f'temp/product_video_{i}.mp4'
        print(f"  제품 영상 다운로드: {url[:60]}...")
        if download_file(url, path):
            downloaded_product_vids.append(path)
            print(f"  ✅ 제품 영상 {i+1} 완료")

    # 이미지 (영상이 없거나 부족할 때)
    for i, img in enumerate(coupang_images[:15]):
        url = img.get('url', '') or img.get('thumb', '')
        if not url: continue
        ext = 'jpg'
        path = f'temp/product_img_{i}.{ext}'
        if download_file(url, path):
            downloaded_product_imgs.append(path)

    print(f"  다운로드 완료 — 영상: {len(downloaded_product_vids)}개, 이미지: {len(downloaded_product_imgs)}개")

    # 구간별 소스 배정
    # 제품 소스가 있으면 우선 배정, 없으면 Gemini AI 생성
    main_pain    = (analysis.get('main_pains') or [''])[0]
    visual_scene = (analysis.get('visual_scenes') or [''])[0]

    # Gemini 프롬프트 (감성/공감 장면용 — 제품 미등장)
    gemini_prompts = {
        'opening':  f'Korean person looking extremely frustrated, dramatic dark lighting, close-up emotional portrait, no product visible, vertical 9:16',
        'empathy':  f'Person struggling with daily problem "{main_pain}", realistic, dark moody, vertical 9:16',
        'cta':      f'Person smiling satisfied, bright warm lighting, lifestyle, vertical 9:16',
    } if not is_wow else {
        'opening':  f'Mysterious dramatic product teaser, dark background, neon lighting, vertical 9:16',
        'cta':      f'Person smiling satisfied, bright warm lighting, lifestyle, vertical 9:16',
    }

    images = []
    prod_img_idx = 0
    prod_vid_idx = 0
    gemini_cache = {}

    for idx, sec in enumerate(sections):
        sec_type = sec['type']
        duration = sec['duration']
        subcut   = sec['subcut']

        # 1순위: 웹앱에서 선택된 Pexels/Pixabay URL
        key_match = f"{sec_type}_{subcut+1}" if subcut > 0 else sec_type
        # (섹션 key 형식 맞추기)
        sec_key_variants = [f"{sec_type}_{subcut+1}", sec_type]
        selected_url = None
        for k in sec_key_variants:
            if k in selected_by_key:
                selected_url = selected_by_key[k]
                break

        if selected_url:
            path = f'temp/selected_{idx}.mp4'
            print(f"  [{idx+1}] 선택된 소스 다운로드...")
            if download_file(selected_url, path):
                images.append({'type':'video','path':path,'section':sec})
                continue

        # 2순위: 제품 영상 (solution/usage/proof/cta 구간)
        if sec_type in ['solution','usage','proof','cta'] and downloaded_product_vids:
            vid_path = downloaded_product_vids[prod_vid_idx % len(downloaded_product_vids)]
            prod_vid_idx += 1
            images.append({'type':'video','path':vid_path,'section':sec})
            print(f"  [{idx+1}] 제품 영상 사용: {sec_type}_{subcut}")
            continue

        # 3순위: 제품 이미지 (solution/usage/proof/cta/opening_2 구간)
        if sec_type in ['solution','usage','proof','cta'] or (sec_type=='opening' and subcut>0):
            if downloaded_product_imgs:
                img_path = downloaded_product_imgs[prod_img_idx % len(downloaded_product_imgs)]
                prod_img_idx += 1
                images.append({'type':'image','path':img_path,'section':sec})
                print(f"  [{idx+1}] 제품 이미지 사용: {sec_type}_{subcut}")
                continue

        # 4순위: Gemini AI (감성/공감 장면)
        prompt_key = sec_type if sec_type in gemini_prompts else 'opening'
        if prompt_key in gemini_prompts:
            if prompt_key not in gemini_cache:
                print(f"  [{idx+1}] Gemini AI 이미지 생성: {sec_type}...")
                try:
                    res = requests.post(
                        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={GEMINI_KEY}',
                        json={'contents':[{'parts':[{'text':gemini_prompts[prompt_key]}]}],'generationConfig':{'responseModalities':['TEXT','IMAGE']}},
                        timeout=40
                    )
                    parts = res.json().get('candidates',[{}])[0].get('content',{}).get('parts',[])
                    img_part = next((p for p in parts if 'inlineData' in p), None)
                    if img_part:
                        path = f'temp/gemini_{prompt_key}.jpg'
                        with open(path,'wb') as f:
                            f.write(base64.b64decode(img_part['inlineData']['data']))
                        gemini_cache[prompt_key] = path
                        print(f"  [{idx+1}] Gemini 완료")
                    else:
                        gemini_cache[prompt_key] = None
                except Exception as e:
                    print(f"  [{idx+1}] Gemini 실패: {e}")
                    gemini_cache[prompt_key] = None

            ai_path = gemini_cache.get(prompt_key)
            if ai_path:
                images.append({'type':'image','path':ai_path,'section':sec})
                continue

        # 5순위: 검정 배경
        images.append({'type':'color','section':sec})
        print(f"  [{idx+1}] 검정 배경 (소스 없음)")

    return images

# =============================================
# 4단계: 클립 생성
# =============================================
def make_clip(source, duration, output_path, is_opening=False):
    duration = max(duration, 0.5)
    vf_scale = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'

    if source['type'] == 'video' and source.get('path') and Path(source['path']).exists():
        cmd = ['ffmpeg', '-i', source['path'], '-vf', vf_scale,
               '-t', str(duration), '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
               output_path, '-y']

    elif source['type'] == 'image' and source.get('path') and Path(source['path']).exists():
        frames = int(duration * 30)
        if is_opening:
            zoom_filter = f'zoompan=z=\'if(eq(on,1),1.3,max(zoom-0.003,1.0))\':d={frames}:s={W}x{H}:fps=30'
        else:
            zoom_filter = f'zoompan=z=\'min(zoom+0.0005,1.15)\':d={frames}:s={W}x{H}:fps=30'
        cmd = ['ffmpeg', '-loop', '1', '-i', source['path'],
               '-vf', f'scale={W*2}:{H*2},{zoom_filter}',
               '-t', str(duration), '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
               output_path, '-y']
    else:
        cmd = ['ffmpeg', '-f', 'lavfi', '-i', f'color=black:size={W}x{H}:rate=30',
               '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-an', output_path, '-y']

    run(cmd)

    if not Path(output_path).exists() and source['type'] == 'image':
        run(['ffmpeg', '-loop', '1', '-i', source['path'], '-vf', vf_scale,
             '-t', str(duration), '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
             output_path, '-y'])

def build_clips(images):
    print("\n[4/6] 클립 생성 중...")
    clips = []
    for idx, img_data in enumerate(images):
        sec = img_data['section']
        out = f'temp/clip_{idx:02d}.mp4'
        make_clip(img_data, sec['duration'], out, is_opening=(idx==0))
        if Path(out).exists():
            clips.append({'path':out,'section':sec})
            print(f"  [{idx+1}] {sec['type']}_{sec['subcut']} {sec['duration']:.1f}초 완료")
        else:
            make_clip({'type':'color'}, sec['duration'], out)
            if Path(out).exists():
                clips.append({'path':out,'section':sec})
    return clips

# =============================================
# 5단계: 자막 (핵심 단어 대형)
# =============================================
def extract_keyword(text):
    stops = ['이','가','은','는','을','를','의','에','서','도','로','으로','와','과','하고','하며','합니다','했습니다','있습니다','입니다','그리고','하지만','때문에','위해']
    parts = re.split(r'[.,!?~\s]+', text)
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and part not in stops:
            cleaned = part[:8]
            for s in stops:
                cleaned = cleaned.replace(s, '')
            if len(cleaned) >= 2:
                return cleaned
    return text[:6]

def build_subtitles_ass(clips, total_duration):
    print("\n[5/6] 자막 생성 중...")

    def fmt(t):
        t = max(0, t)
        return f"{int(t//3600)}:{int((t%3600)//60):02d}:{int(t%60):02d}.{int((t%1)*100):02d}"

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Hook,Noto Sans CJK KR,120,&H00FFE500,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,8,5,5,40,40,80,1
Style: Main,Noto Sans CJK KR,90,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,6,4,5,40,40,80,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    prev_sent = None
    kw_idx    = 0

    for clip_data in clips:
        sec      = clip_data['section']
        start    = sec['start']
        end      = sec['end']
        text     = sec['text']
        sec_type = sec['type']
        subcut   = sec['subcut']

        if text != prev_sent:
            kw_idx = 0
            prev_sent = text

        # 핵심 단어 추출
        words = [w.strip() for w in re.split(r'[.,!?~\s]+', text) if len(w.strip()) >= 2]
        kw = words[kw_idx % len(words)] if words else text[:6]
        kw = kw[:8]  # 최대 8자
        kw_idx += 1

        style = 'Hook' if (sec_type == 'opening' and subcut == 0) else 'Main'
        ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},{style},,0,0,0,,{kw}\n"

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)
    print(f"  자막 {len(clips)}개 완료")
    return path

# =============================================
# 6단계: 최종 합성
# =============================================
def final_render(clips, ass_path):
    print("\n[6/6] 최종 영상 합성 중...")

    concat_file = 'temp/concat.txt'
    with open(concat_file, 'w') as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c['path'])}'\n")

    run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c', 'copy', 'temp/merged.mp4', '-y'])
    if not Path('temp/merged.mp4').exists():
        raise Exception("클립 연결 실패")
    print("  클립 연결 완료")

    abs_ass = os.path.abspath(ass_path).replace('\\','/').replace(':','\\:')

    r = run(['ffmpeg', '-i', 'temp/merged.mp4', '-i', 'temp/audio.mp3',
             '-vf', f"ass='{abs_ass}'",
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
             '-c:a', 'aac', '-b:a', '128k', '-shortest',
             'output/final.mp4', '-y'])

    if not Path('output/final.mp4').exists():
        print("  자막 합성 실패 — 자막 없이 재시도")
        run(['ffmpeg', '-i', 'temp/merged.mp4', '-i', 'temp/audio.mp3',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
             '-c:a', 'aac', '-b:a', '128k', '-shortest',
             'output/final.mp4', '-y'])

    if Path('output/final.mp4').exists():
        size = Path('output/final.mp4').stat().st_size / 1024 / 1024
        print(f"\n=== 렌더링 완료 ===\n파일: output/final.mp4 ({size:.1f}MB)")
    else:
        raise Exception("최종 영상 생성 실패")

# =============================================
# 메인
# =============================================
if __name__ == '__main__':
    try:
        install_fonts()
        sentences, narration, duration, timepoints = generate_tts()
        sections = design_sections(sentences, duration, timepoints)
        images   = collect_sources(sections)
        clips    = build_clips(images)
        ass_path = build_subtitles_ass(clips, duration)
        final_render(clips, ass_path)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback; traceback.print_exc()
        exit(1)
