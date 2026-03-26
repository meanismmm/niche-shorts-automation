import os
import json
import requests
import subprocess
import base64
from pathlib import Path

# =============================================
# 환경변수 로드
# =============================================
SCRIPT_DATA   = json.loads(os.environ.get('SCRIPT_DATA', '{}'))
SOURCES_DATA  = json.loads(os.environ.get('SOURCES_DATA', '{}'))
PEXELS_KEY    = os.environ.get('PEXELS_API_KEY', '')
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY', '')
GCLOUD_KEY    = os.environ.get('GOOGLE_CLOUD_KEY', '')

# 출력 디렉토리 생성
Path('output').mkdir(exist_ok=True)
Path('temp').mkdir(exist_ok=True)

print("=== 니치 쇼츠 자동 렌더링 시작 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

# =============================================
# 1단계: TTS 음성 생성
# =============================================
def generate_tts():
    print("\n[1/5] TTS 음성 생성 중...")

    is_wow = SCRIPT_DATA.get('type') == 'wow'
    if is_wow:
        narration = ' '.join([
            SCRIPT_DATA.get('opening', ''),
            SCRIPT_DATA.get('proof', ''),
            SCRIPT_DATA.get('usage', ''),
            SCRIPT_DATA.get('cta', ''),
        ])
    else:
        narration = ' '.join([
            SCRIPT_DATA.get('opening', ''),
            SCRIPT_DATA.get('empathy', ''),
            SCRIPT_DATA.get('solution', ''),
            SCRIPT_DATA.get('cta', ''),
        ])

    # 단위 변환
    import re
    narration = re.sub(r'(\d+\.?\d*)\s*L\b', r'\1리터', narration)
    narration = re.sub(r'(\d+\.?\d*)\s*ml\b', r'\1밀리리터', narration, flags=re.IGNORECASE)
    narration = re.sub(r'(\d+\.?\d*)\s*kg\b', r'\1킬로그램', narration)
    narration = re.sub(r'(\d+\.?\d*)\s*g\b', r'\1그램', narration)
    narration = re.sub(r'(\d+\.?\d*)\s*cm\b', r'\1센티미터', narration)
    narration = re.sub(r'(\d+\.?\d*)\s*%', r'\1퍼센트', narration)

    # 카테고리별 목소리 매핑
    cat_key = SCRIPT_DATA.get('category', {}).get('key', 'gadget')
    voice_map = {
        'pet':        ('ko-KR-Wavenet-A', 'FEMALE'),
        'single':     ('ko-KR-Wavenet-D', 'MALE'),
        'sleep':      ('ko-KR-Wavenet-A', 'FEMALE'),
        'homeoffice': ('ko-KR-Wavenet-D', 'MALE'),
        'kitchen':    ('ko-KR-Wavenet-B', 'FEMALE'),
        'gadget':     ('ko-KR-Wavenet-C', 'MALE'),
    }
    voice_name, voice_gender = voice_map.get(cat_key, ('ko-KR-Wavenet-C', 'MALE'))

    payload = {
        'input': {'text': narration},
        'voice': {'languageCode': 'ko-KR', 'name': voice_name, 'ssmlGender': voice_gender},
        'audioConfig': {'audioEncoding': 'MP3', 'speakingRate': 1.15, 'pitch': 1.5}
    }

    res = requests.post(
        f'https://texttospeech.googleapis.com/v1/text:synthesize?key={GCLOUD_KEY}',
        json=payload
    )
    data = res.json()

    if 'audioContent' not in data:
        print(f"TTS 오류: {data}")
        # 무음 파일 생성 (폴백)
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
                       '-t', '25', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        return narration, 25.0

    audio_bytes = base64.b64decode(data['audioContent'])
    with open('temp/audio.mp3', 'wb') as f:
        f.write(audio_bytes)

    # 음성 길이 확인
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip() or '25')
    print(f"  음성 생성 완료: {duration:.1f}초")
    return narration, duration

# =============================================
# 2단계: 영상 소스 다운로드
# =============================================
def download_sources():
    print("\n[2/5] 영상 소스 다운로드 중...")
    downloaded = {}
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    section_keys = ['opening', 'proof', 'usage', 'cta'] if is_wow else ['opening', 'empathy', 'solution', 'cta']

    for i, key in enumerate(section_keys):
        source = SOURCES_DATA.get(key, {})
        selected = source.get('selected')

        if selected and selected.get('idx') == 'ai':
            # AI 이미지 — Gemini로 재생성
            print(f"  [{key}] AI 이미지 생성 중...")
            img_path = generate_ai_image(key, i)
            if img_path:
                downloaded[key] = {'type': 'image', 'path': img_path}
            else:
                downloaded[key] = {'type': 'color', 'color': 'black'}

        elif selected and selected.get('data', {}).get('url'):
            # Pexels 영상 다운로드
            url = selected['data']['url']
            print(f"  [{key}] Pexels 영상 다운로드 중...")
            path = f'temp/src_{key}.mp4'
            try:
                r = requests.get(url, timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded[key] = {'type': 'video', 'path': path}
                print(f"  [{key}] 다운로드 완료")
            except Exception as e:
                print(f"  [{key}] 다운로드 실패: {e}, 컬러 배경 사용")
                downloaded[key] = {'type': 'color', 'color': 'black'}
        else:
            # 소스 없음 — Pexels 자동 검색
            print(f"  [{key}] 자동 검색 중...")
            product = SCRIPT_DATA.get('product', 'lifestyle')
            videos = search_pexels(product)
            if videos:
                url = videos[0].get('url')
                path = f'temp/src_{key}.mp4'
                r = requests.get(url, timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded[key] = {'type': 'video', 'path': path}
            else:
                downloaded[key] = {'type': 'color', 'color': 'black'}

    return downloaded

def search_pexels(keyword, per_page=1):
    try:
        res = requests.get(
            f'https://api.pexels.com/videos/search?query={keyword}&per_page={per_page}&orientation=portrait',
            headers={'Authorization': PEXELS_KEY}, timeout=15
        )
        videos = res.json().get('videos', [])
        result = []
        for v in videos:
            url = next((f['link'] for f in v.get('video_files', []) if f.get('quality') == 'sd'), None)
            if not url and v.get('video_files'):
                url = v['video_files'][0]['link']
            if url:
                result.append({'url': url, 'duration': v.get('duration', 5)})
        return result
    except:
        return []

def generate_ai_image(key, idx):
    try:
        product = SCRIPT_DATA.get('product', '')
        prompts = {
            'opening': f'Dramatic cinematic shot related to {product}, dark moody atmosphere, high contrast, professional photography',
            'proof':   f'{product} close-up detail shot, studio lighting, clean background, product photography',
            'solution': f'{product} lifestyle shot, natural lighting, warm tones, person using the product happily',
            'empathy': f'Person looking thoughtful or concerned, cinematic, dark moody tone, no text',
        }
        prompt = prompts.get(key, f'{product} product shot, professional photography')

        res = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={GEMINI_KEY}',
            json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}},
            timeout=30
        )
        data = res.json()
        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        img_part = next((p for p in parts if 'inlineData' in p), None)
        if not img_part:
            return None

        img_data = base64.b64decode(img_part['inlineData']['data'])
        path = f'temp/ai_{key}.jpg'
        with open(path, 'wb') as f:
            f.write(img_data)
        return path
    except Exception as e:
        print(f"  AI 이미지 생성 실패: {e}")
        return None

# =============================================
# 3단계: 구간별 클립 생성
# =============================================
def make_clip(source, duration, output_path, speed=1.0):
    """소스(영상/이미지/컬러)를 지정 길이의 9:16 흑백 클립으로 변환"""
    w, h = 1080, 1920

    if source['type'] == 'video':
        cmd = [
            'ffmpeg', '-i', source['path'],
            '-vf', f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray,setpts={1/speed}*PTS',
            '-af', f'atempo={speed}' if speed != 1.0 else 'anull',
            '-t', str(duration),
            '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-an',
            output_path, '-y'
        ]
    elif source['type'] == 'image':
        cmd = [
            'ffmpeg', '-loop', '1', '-i', source['path'],
            '-vf', f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray',
            '-t', str(duration),
            '-r', '30', '-c:v', 'libx264', '-preset', 'fast', '-an',
            output_path, '-y'
        ]
    else:  # color
        cmd = [
            'ffmpeg',
            '-f', 'lavfi', '-i', f'color=black:size={w}x{h}:rate=30',
            '-t', str(duration),
            '-c:v', 'libx264', '-preset', 'fast', '-an',
            output_path, '-y'
        ]

    subprocess.run(cmd, capture_output=True)

def build_clips(sources, total_duration):
    print("\n[3/5] 구간별 클립 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    # 구간별 시간 배분 (총 duration 기준)
    if is_wow:
        ratios = {'opening': 0.12, 'proof': 0.33, 'usage': 0.40, 'cta': 0.15}
        speeds = {'opening': 1.2, 'proof': 0.8, 'usage': 1.05, 'cta': 1.0}
    else:
        ratios = {'opening': 0.12, 'empathy': 0.30, 'solution': 0.43, 'cta': 0.15}
        speeds = {'opening': 1.15, 'empathy': 1.0, 'solution': 1.0, 'cta': 1.0}

    clips = []
    for key, ratio in ratios.items():
        dur = total_duration * ratio
        source = sources.get(key, {'type': 'color', 'color': 'black'})
        out_path = f'temp/clip_{key}.mp4'
        make_clip(source, dur, out_path, speeds.get(key, 1.0))
        clips.append(out_path)
        print(f"  [{key}] {dur:.1f}초 클립 생성 완료")

    return clips

# =============================================
# 4단계: 자막 생성 (SRT)
# =============================================
def build_subtitles(narration, total_duration):
    print("\n[4/5] 자막 파일 생성 중...")

    # 문장 분리
    import re
    sentences = re.split(r'(?<=[.!?])\s+', narration.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        sentences = [narration]

    # 균등 시간 배분
    dur_per = total_duration / len(sentences)

    srt_lines = []
    for i, sent in enumerate(sentences):
        start = i * dur_per
        end = (i + 1) * dur_per - 0.1

        def fmt_time(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_lines.append(f"{i+1}")
        srt_lines.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        srt_lines.append(sent)
        srt_lines.append("")

    srt_path = 'temp/subtitles.srt'
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))

    print(f"  자막 {len(sentences)}개 문장 생성 완료")
    return srt_path

# =============================================
# 5단계: 최종 영상 합성
# =============================================
def final_render(clips, srt_path):
    print("\n[5/5] 최종 영상 합성 중...")

    # 클립 연결 목록 파일 생성
    concat_file = 'temp/concat.txt'
    with open(concat_file, 'w') as f:
        for clip in clips:
            if Path(clip).exists():
                f.write(f"file '{clip}'\n")

    # 클립 연결
    subprocess.run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
        '-c', 'copy', 'temp/merged.mp4', '-y'
    ], capture_output=True)

    # 자막 + 음성 합성
    # 자막 스타일: 흰색 텍스트 + 검정 외곽선 + 노란 강조 (첫 문장)
    subtitle_style = (
        "FontName=Noto Sans CJK KR,Bold,"
        "FontSize=18,"
        "PrimaryColour=&H00FFFFFF,"   # 흰색
        "OutlineColour=&H00000000,"   # 검정 외곽선
        "BackColour=&H80000000,"      # 반투명 배경
        "Outline=3,"
        "Shadow=1,"
        "Alignment=2,"                # 하단 중앙
        "MarginV=80"
    )

    subprocess.run([
        'ffmpeg',
        '-i', 'temp/merged.mp4',
        '-i', 'temp/audio.mp3',
        '-vf', f"subtitles=temp/subtitles.srt:force_style='{subtitle_style}'",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        'output/final.mp4', '-y'
    ], capture_output=True)

    if Path('output/final.mp4').exists():
        size = Path('output/final.mp4').stat().st_size / 1024 / 1024
        print(f"\n=== 렌더링 완료 ===")
        print(f"파일: output/final.mp4")
        print(f"크기: {size:.1f}MB")
    else:
        print("ERROR: 최종 영상 생성 실패")
        raise Exception("렌더링 실패")

# =============================================
# 메인 실행
# =============================================
if __name__ == '__main__':
    try:
        # 1. TTS 음성 생성
        narration, duration = generate_tts()

        # 2. 소스 다운로드
        sources = download_sources()

        # 3. 클립 생성
        clips = build_clips(sources, duration)

        # 4. 자막 생성
        srt_path = build_subtitles(narration, duration)

        # 5. 최종 합성
        final_render(clips, srt_path)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
