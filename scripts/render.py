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

print("=== 니치 쇼츠 자동 렌더링 v2.1 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

W, H = 1080, 1920

# =============================================
# 유틸
# =============================================
def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  CMD 오류: {result.stderr[-400:]}")
    return result

def convert_units(text):
    text = re.sub(r'(\d+\.?\d*)\s*L\b',  r'\1리터',     text)
    text = re.sub(r'(\d+\.?\d*)\s*ml\b', r'\1밀리리터', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+\.?\d*)\s*kg\b', r'\1킬로그램', text)
    text = re.sub(r'(\d+\.?\d*)\s*g\b',  r'\1그램',     text)
    text = re.sub(r'(\d+\.?\d*)\s*cm\b', r'\1센티미터', text)
    text = re.sub(r'(\d+\.?\d*)\s*%',    r'\1퍼센트',   text)
    return text

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
# 1단계: TTS 음성 생성 (타임포인트)
# =============================================
def generate_tts():
    print("\n[1/6] TTS 음성 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    if is_wow:
        sentences = [
            SCRIPT_DATA.get('opening', ''),
            SCRIPT_DATA.get('proof', ''),
            SCRIPT_DATA.get('usage', ''),
            SCRIPT_DATA.get('cta', ''),
        ]
    else:
        sentences = [
            SCRIPT_DATA.get('opening', ''),
            SCRIPT_DATA.get('empathy', ''),
            SCRIPT_DATA.get('solution', ''),
            SCRIPT_DATA.get('cta', ''),
        ]

    sentences = [convert_units(s.strip()) for s in sentences if s.strip()]
    narration = ' '.join(sentences)

    cat_key   = SCRIPT_DATA.get('category', {}).get('key', 'gadget')
    voice_map = {
        'pet':        ('ko-KR-Wavenet-A', 'FEMALE'),
        'single':     ('ko-KR-Wavenet-D', 'MALE'),
        'sleep':      ('ko-KR-Wavenet-A', 'FEMALE'),
        'homeoffice': ('ko-KR-Wavenet-D', 'MALE'),
        'kitchen':    ('ko-KR-Wavenet-B', 'FEMALE'),
        'gadget':     ('ko-KR-Wavenet-C', 'MALE'),
    }
    voice_name, voice_gender = voice_map.get(cat_key, ('ko-KR-Wavenet-C', 'MALE'))

    # SSML 마크 삽입
    ssml_parts = ['<speak>']
    for i, s in enumerate(sentences):
        ssml_parts.append(f'<mark name="s{i}"/>{s}')
    ssml_parts.append('</speak>')
    ssml = ''.join(ssml_parts)

    try:
        res = requests.post(
            f'https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={GCLOUD_KEY}',
            json={
                'input': {'ssml': ssml},
                'voice': {'languageCode': 'ko-KR', 'name': voice_name, 'ssmlGender': voice_gender},
                'audioConfig': {'audioEncoding': 'MP3', 'speakingRate': 1.15, 'pitch': 1.5},
                'enableTimePointing': ['SSML_MARK']
            },
            timeout=30
        )
        data = res.json()
        if 'audioContent' not in data:
            raise Exception(f"TTS 오류: {data}")

        with open('temp/audio.mp3', 'wb') as f:
            f.write(base64.b64decode(data['audioContent']))

        timepoints = {}
        for tp in data.get('timepoints', []):
            mark = tp.get('markName', '')
            if mark.startswith('s'):
                timepoints[int(mark[1:])] = tp.get('timeSeconds', 0)

        result = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'])
        duration = float(result.stdout.strip() or '28')
        print(f"  TTS 완료: {duration:.1f}초, 타임포인트: {timepoints}")
        return sentences, narration, duration, timepoints

    except Exception as e:
        print(f"  TTS 실패: {e}")
        run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '28', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        n = len(sentences)
        timepoints = {i: i * (28 / max(n, 1)) for i in range(n)}
        return sentences, narration, 28.0, timepoints

# =============================================
# 2단계: 구간 설계 (10개, 2~3초씩)
# =============================================
def design_sections(sentences, total_duration, timepoints):
    """
    문장 4개를 받아서 10개 구간으로 세분화.
    각 구간은 2~3초로 빠른 컷 전환.
    """
    print("\n[2/6] 구간 설계 중 (10개 빠른 컷)...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    # 문장별 실제 시간 범위
    n = len(sentences)
    seg_times = []
    for i in range(n):
        start = timepoints.get(i, i * total_duration / n)
        end   = timepoints.get(i+1, start + total_duration / n) if i+1 < n else total_duration
        seg_times.append((start, end))

    # 각 문장을 2~3개 서브컷으로 분할
    sections = []
    for i, (start, end) in enumerate(seg_times):
        seg_dur = end - start
        # 서브컷 수: 짧으면 1개, 길면 2~3개
        if seg_dur < 3:
            n_cuts = 1
        elif seg_dur < 6:
            n_cuts = 2
        else:
            n_cuts = 3

        cut_dur = seg_dur / n_cuts
        for j in range(n_cuts):
            cut_start = start + j * cut_dur
            cut_end   = start + (j+1) * cut_dur
            # 구간 유형 결정
            if i == 0:
                sec_type = 'opening'
            elif i == n-1:
                sec_type = 'cta'
            elif is_wow:
                sec_type = ['proof', 'usage'][min(i-1, 1)]
            else:
                sec_type = ['empathy', 'solution'][min(i-1, 1)]

            sections.append({
                'type':     sec_type,
                'sentence': i,
                'subcut':   j,
                'start':    cut_start,
                'end':      cut_end,
                'duration': cut_dur,
                'text':     sentences[i],
            })

    print(f"  총 {len(sections)}개 구간 설계 완료")
    for idx, s in enumerate(sections):
        print(f"  [{idx+1}] {s['type']} {s['subcut']+1} — {s['duration']:.1f}초")
    return sections

# =============================================
# 3단계: 구간별 이미지 생성
# =============================================
def generate_images_for_sections(sections):
    print("\n[3/6] 구간별 이미지/영상 수집 중...")
    is_wow  = SCRIPT_DATA.get('type') == 'wow'
    product = SCRIPT_DATA.get('product', '')
    analysis = SCRIPT_DATA.get('analysis', {})

    main_pain    = (analysis.get('main_pains') or [''])[0]
    visual_scene = (analysis.get('visual_scenes') or [''])[0]

    # 구간 유형별 프롬프트 (다양하게)
    prompt_variants = {
        'opening': [
            f'Korean person showing extreme frustration, close-up face, dramatic dark lighting, cinematic, vertical 9:16',
            f'Problem situation related to "{main_pain}", realistic, dark moody, vertical 9:16',
            f'Dramatic tension shot, person stressed, cinematic portrait, vertical 9:16',
        ],
        'empathy': [
            f'Person struggling with daily inconvenience, realistic indoor scene, vertical 9:16',
            f'Close-up of the problem "{main_pain}", detailed shot, vertical 9:16',
            f'Frustrated person at home, relatable situation, vertical 9:16',
        ],
        'solution': [
            f'{product} product shot, studio lighting, clean white background, vertical 9:16',
            f'Person happily using {product}, warm lighting, satisfied expression, vertical 9:16',
            f'{visual_scene or product + " in use"}, lifestyle photography, bright colors, vertical 9:16',
        ],
        'proof': [
            f'{product} detail macro shot, professional product photography, vertical 9:16',
            f'{product} features close-up, high contrast lighting, vertical 9:16',
        ],
        'usage': [
            f'Person using {product} in daily life, lifestyle shot, vertical 9:16',
            f'{product} real life usage, natural lighting, vertical 9:16',
        ],
        'cta': [
            f'{product} product on minimal background, premium spotlight, vertical 9:16',
            f'Person smiling holding {product}, satisfied, bright lighting, vertical 9:16',
        ],
    }

    # 먼저 웹앱에서 선택한 소스 확인
    selected_sources = {}
    for key, val in SOURCES_DATA.items():
        sel = val.get('selected')
        if sel and sel.get('data', {}).get('url'):
            selected_sources[key] = sel['data']['url']

    images = []
    used_prompts = {}  # 같은 유형 반복 방지

    for idx, sec in enumerate(sections):
        sec_type = sec['type']
        subcut   = sec['subcut']

        # Pexels 선택 소스 있으면 우선 사용
        if sec_type in selected_sources and subcut == 0:
            url  = selected_sources[sec_type]
            path = f'temp/src_{sec_type}_video.mp4'
            if not Path(path).exists():
                print(f"  [{idx+1}] Pexels 영상 다운로드...")
                try:
                    r = requests.get(url, timeout=60, stream=True)
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                except Exception as e:
                    print(f"  다운로드 실패: {e}")
                    path = None
            if path and Path(path).exists():
                images.append({'type': 'video', 'path': path, 'section': sec})
                continue

        # Gemini 이미지 생성
        variants = prompt_variants.get(sec_type, [f'{product} lifestyle, vertical 9:16'])
        prompt_idx = used_prompts.get(sec_type, 0)
        prompt = variants[prompt_idx % len(variants)]
        used_prompts[sec_type] = prompt_idx + 1

        print(f"  [{idx+1}] Gemini 이미지 생성: {sec_type}_{subcut}...")
        try:
            res = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key={GEMINI_KEY}',
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}
                },
                timeout=40
            )
            parts = res.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
            img_part = next((p for p in parts if 'inlineData' in p), None)
            if img_part:
                path = f'temp/ai_{idx}_{sec_type}_{subcut}.jpg'
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(img_part['inlineData']['data']))
                images.append({'type': 'image', 'path': path, 'section': sec})
                print(f"  [{idx+1}] 완료")
            else:
                images.append({'type': 'color', 'section': sec})
        except Exception as e:
            print(f"  [{idx+1}] 실패: {e}")
            images.append({'type': 'color', 'section': sec})

    return images

# =============================================
# 4단계: 클립 생성 (빠른 컷, 2~3초)
# =============================================
def make_clip(source, duration, output_path, is_opening=False):
    duration = max(duration, 0.5)
    vf_scale = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'

    if source['type'] == 'video' and source.get('path') and Path(source['path']).exists():
        # 영상: 시작점 랜덤화로 다양성 확보
        cmd = ['ffmpeg', '-i', source['path'],
               '-vf', vf_scale,
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
               output_path, '-y']

    elif source['type'] == 'image' and source.get('path') and Path(source['path']).exists():
        # 이미지: 줌인/줌아웃 효과 교대
        frames = int(duration * 30)
        if is_opening:
            # 오프닝: 빠른 줌인
            zoom_filter = f'zoompan=z=\'if(eq(on,1),1.3,max(zoom-0.003,1.0))\':d={frames}:s={W}x{H}:fps=30'
        else:
            zoom_filter = f'zoompan=z=\'min(zoom+0.0006,1.2)\':d={frames}:s={W}x{H}:fps=30'

        cmd = ['ffmpeg', '-loop', '1', '-i', source['path'],
               '-vf', f'scale={W*2}:{H*2},{zoom_filter}',
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
               output_path, '-y']
    else:
        cmd = ['ffmpeg', '-f', 'lavfi',
               '-i', f'color=black:size={W}x{H}:rate=30',
               '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']

    run(cmd)

    # 줌 실패 시 단순 이미지
    if not Path(output_path).exists() and source['type'] == 'image':
        run(['ffmpeg', '-loop', '1', '-i', source['path'],
             '-vf', vf_scale, '-t', str(duration), '-r', '30',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an',
             output_path, '-y'])

def build_clips(images):
    print("\n[4/6] 클립 생성 중...")
    clips = []
    for idx, img_data in enumerate(images):
        sec      = img_data['section']
        duration = sec['duration']
        out      = f'temp/clip_{idx:02d}.mp4'
        is_open  = (idx == 0)
        make_clip(img_data, duration, out, is_opening=is_open)
        if Path(out).exists():
            clips.append({'path': out, 'section': sec})
            print(f"  [{idx+1}] {sec['type']}_{sec['subcut']} {duration:.1f}초 완료")
        else:
            # 검정 배경 대체
            make_clip({'type': 'color'}, duration, out)
            if Path(out).exists():
                clips.append({'path': out, 'section': sec})
    return clips

# =============================================
# 5단계: 자막 (핵심 단어 대형, 중앙)
# =============================================
def extract_keywords(text):
    """문장에서 핵심 키워드 2~5자 추출"""
    # 조사/어미 제거 후 핵심 명사/동사 추출
    stopwords = ['이', '가', '은', '는', '을', '를', '의', '에', '서', '도', '로', '으로',
                 '와', '과', '하고', '하며', '합니다', '했습니다', '있습니다', '입니다',
                 '그리고', '하지만', '그런데', '때문에', '위해서']

    # 문장 분리 (마침표, 쉼표 기준)
    parts = re.split(r'[.,!?~]', text)
    keywords = []

    for part in parts:
        part = part.strip()
        if len(part) >= 2:
            # 핵심 부분 (너무 길면 앞부분만)
            if len(part) > 8:
                part = part[:8]
            # 불필요한 어미 제거
            for sw in stopwords:
                part = part.replace(sw, '')
            part = part.strip()
            if len(part) >= 2:
                keywords.append(part)

    return keywords[:3] if keywords else [text[:6]]

def build_subtitles_ass(clips, total_duration):
    print("\n[5/6] 자막 생성 중 (핵심 단어 대형)...")

    def fmt(t):
        t  = max(0, t)
        h  = int(t // 3600)
        m  = int((t % 3600) // 60)
        s  = int(t % 60)
        cs = int((t % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # ASS 스타일 — 핵심 단어, 화면 중앙 대형, 그림자 강조
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Main,Noto Sans CJK KR,95,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,6,4,5,40,40,80,1
Style: Hook,Noto Sans CJK KR,120,&H00FFE500,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,4,0,1,8,5,5,40,40,80,1
Style: Sub,Noto Sans CJK KR,72,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,0,0,100,100,2,0,3,4,3,2,60,60,120,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    prev_text = None

    for idx, clip_data in enumerate(clips):
        sec      = clip_data['section']
        start    = sec['start']
        end      = sec['end']
        text     = sec['text']
        sec_type = sec['type']
        subcut   = sec['subcut']

        # 같은 문장의 첫 서브컷에만 자막 표시 (중복 방지)
        if text == prev_text and subcut > 0:
            # 서브컷에서는 핵심 단어만 표시
            keywords = extract_keywords(text)
            if keywords and idx < len(keywords):
                kw = keywords[subcut % len(keywords)]
                style = 'Hook' if sec_type == 'opening' else 'Main'
                ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},{style},,0,0,0,,{kw}\n"
        else:
            # 첫 서브컷: 핵심 단어 대형 표시
            keywords = extract_keywords(text)
            kw = keywords[0] if keywords else text[:6]

            if sec_type == 'opening' and subcut == 0:
                # 오프닝: 최대형 노란색
                style = 'Hook'
            elif sec_type in ['solution', 'usage']:
                # 해결/활용: 흰색 대형
                style = 'Main'
            else:
                style = 'Main'

            ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},{style},,0,0,0,,{kw}\n"

        prev_text = text

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

    run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
         '-c', 'copy', 'temp/merged.mp4', '-y'])

    if not Path('temp/merged.mp4').exists():
        raise Exception("클립 연결 실패")
    print("  클립 연결 완료")

    abs_ass = os.path.abspath(ass_path).replace('\\', '/').replace(':', '\\:')

    # 자막 + 음성
    r = run([
        'ffmpeg',
        '-i', 'temp/merged.mp4',
        '-i', 'temp/audio.mp3',
        '-vf', f"ass='{abs_ass}'",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        'output/final.mp4', '-y'
    ])

    if not Path('output/final.mp4').exists():
        print("  자막 합성 실패 — 자막 없이 재시도")
        run([
            'ffmpeg',
            '-i', 'temp/merged.mp4',
            '-i', 'temp/audio.mp3',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest',
            'output/final.mp4', '-y'
        ])

    if Path('output/final.mp4').exists():
        size = Path('output/final.mp4').stat().st_size / 1024 / 1024
        print(f"\n=== 렌더링 완료 ===")
        print(f"파일: output/final.mp4 ({size:.1f}MB)")
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
        images   = generate_images_for_sections(sections)
        clips    = build_clips(images)
        ass_path = build_subtitles_ass(clips, duration)
        final_render(clips, ass_path)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
