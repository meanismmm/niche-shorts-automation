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

Path('output').mkdir(exist_ok=True)
Path('temp').mkdir(exist_ok=True)

print("=== 니치 쇼츠 자동 렌더링 시작 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

# =============================================
# 유틸
# =============================================
def run(cmd, check=False):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  CMD 오류: {result.stderr[-300:]}")
    return result

def convert_units(text):
    text = re.sub(r'(\d+\.?\d*)\s*L\b',   r'\1리터',     text)
    text = re.sub(r'(\d+\.?\d*)\s*ml\b',  r'\1밀리리터', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+\.?\d*)\s*kg\b',  r'\1킬로그램', text)
    text = re.sub(r'(\d+\.?\d*)\s*g\b',   r'\1그램',     text)
    text = re.sub(r'(\d+\.?\d*)\s*cm\b',  r'\1센티미터', text)
    text = re.sub(r'(\d+\.?\d*)\s*%',     r'\1퍼센트',   text)
    return text

# =============================================
# 1단계: 한국어 폰트 설치
# =============================================
def install_fonts():
    print("\n[0/5] 한국어 폰트 설치 중...")
    run(['sudo', 'apt-get', 'install', '-y', 'fonts-noto-cjk'])
    run(['fc-cache', '-fv'])
    print("  폰트 설치 완료")

# =============================================
# 2단계: TTS 음성 생성
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
    narration = convert_units(narration)

    # 카테고리별 목소리
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

    try:
        res = requests.post(
            f'https://texttospeech.googleapis.com/v1/text:synthesize?key={GCLOUD_KEY}',
            json={
                'input': {'text': narration},
                'voice': {'languageCode': 'ko-KR', 'name': voice_name, 'ssmlGender': voice_gender},
                'audioConfig': {'audioEncoding': 'MP3', 'speakingRate': 1.15, 'pitch': 1.5}
            }, timeout=30
        )
        data = res.json()
        if 'audioContent' not in data:
            raise Exception(f"TTS 오류: {data}")

        with open('temp/audio.mp3', 'wb') as f:
            f.write(base64.b64decode(data['audioContent']))

        result = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'])
        duration = float(result.stdout.strip() or '25')
        print(f"  음성 생성 완료: {duration:.1f}초")
        return narration, duration

    except Exception as e:
        print(f"  TTS 실패: {e}, 무음 사용")
        run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '25', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        return narration, 25.0

# =============================================
# 3단계: 소스 다운로드
# =============================================
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

def generate_ai_image(prompt):
    try:
        res = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={GEMINI_KEY}',
            json={'contents': [{'parts': [{'text': prompt}]}],
                  'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}},
            timeout=30
        )
        parts = res.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
        img_part = next((p for p in parts if 'inlineData' in p), None)
        if not img_part:
            return None
        path = 'temp/ai_img.jpg'
        with open(path, 'wb') as f:
            f.write(base64.b64decode(img_part['inlineData']['data']))
        return path
    except Exception as e:
        print(f"  AI 이미지 실패: {e}")
        return None

def download_sources():
    print("\n[2/5] 소스 다운로드 중...")
    downloaded = {}
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    product = SCRIPT_DATA.get('product', 'lifestyle')
    section_keys = ['opening', 'proof', 'usage', 'cta'] if is_wow else ['opening', 'empathy', 'solution', 'cta']

    for key in section_keys:
        source = SOURCES_DATA.get(key, {})
        selected = source.get('selected')

        if selected and selected.get('idx') == 'ai':
            print(f"  [{key}] AI 이미지 재생성 중...")
            prompts = {
                'opening':  f'dramatic scene showing person frustrated without {product}, dark moody cinematic',
                'solution': f'{product} being used happily, warm lifestyle photography, clean background',
                'proof':    f'close-up detail of {product}, studio lighting, product photography',
            }
            img = generate_ai_image(prompts.get(key, f'{product} product shot'))
            downloaded[key] = {'type': 'image', 'path': img} if img else {'type': 'color'}

        elif selected and selected.get('data', {}).get('url'):
            url = selected['data']['url']
            print(f"  [{key}] Pexels 영상 다운로드 중...")
            path = f'temp/src_{key}.mp4'
            try:
                r = requests.get(url, timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded[key] = {'type': 'video', 'path': path}
                print(f"  [{key}] 완료")
            except Exception as e:
                print(f"  [{key}] 실패: {e}")
                downloaded[key] = {'type': 'color'}
        else:
            print(f"  [{key}] 자동 검색: {product}")
            videos = search_pexels(product)
            if videos:
                path = f'temp/src_{key}.mp4'
                r = requests.get(videos[0]['url'], timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded[key] = {'type': 'video', 'path': path}
            else:
                downloaded[key] = {'type': 'color'}

    return downloaded

# =============================================
# 4단계: 구간별 클립 생성
# =============================================
def make_clip(source, duration, output_path, speed=1.0):
    w, h = 1080, 1920
    vf_base = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray'

    if source['type'] == 'video' and source.get('path') and Path(source['path']).exists():
        pts = f'setpts={1/speed:.4f}*PTS'
        cmd = ['ffmpeg', '-i', source['path'],
               '-vf', f'{vf_base},{pts}',
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']
    elif source['type'] == 'image' and source.get('path') and Path(source['path']).exists():
        cmd = ['ffmpeg', '-loop', '1', '-i', source['path'],
               '-vf', vf_base,
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']
    else:
        cmd = ['ffmpeg', '-f', 'lavfi',
               '-i', f'color=black:size={w}x{h}:rate=30',
               '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']

    run(cmd)

def build_clips(sources, total_duration):
    print("\n[3/5] 구간별 클립 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    if is_wow:
        ratios = {'opening': 0.12, 'proof': 0.33, 'usage': 0.40, 'cta': 0.15}
        speeds = {'opening': 1.2,  'proof': 0.8,  'usage': 1.05, 'cta': 1.0}
    else:
        ratios = {'opening': 0.12, 'empathy': 0.30, 'solution': 0.43, 'cta': 0.15}
        speeds = {'opening': 1.15, 'empathy': 1.0,  'solution': 1.0,  'cta': 1.0}

    clips = []
    for key, ratio in ratios.items():
        dur = max(total_duration * ratio, 1.0)
        src = sources.get(key, {'type': 'color'})
        out = f'temp/clip_{key}.mp4'
        make_clip(src, dur, out, speeds.get(key, 1.0))
        if Path(out).exists():
            clips.append(out)
            print(f"  [{key}] {dur:.1f}초 완료")
        else:
            print(f"  [{key}] 클립 생성 실패 — 검정 배경으로 대체")
            make_clip({'type': 'color'}, dur, out)
            clips.append(out)

    return clips

# =============================================
# 5단계: 자막 생성 (ASS 형식 — FFmpeg 호환성 최고)
# =============================================
def build_subtitles_ass(narration, total_duration):
    print("\n[4/5] 자막 파일 생성 중...")

    sentences = re.split(r'(?<=[.!?])\s+', narration.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        sentences = [narration]

    dur_per = total_duration / len(sentences)

    def fmt(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        cs = int((t % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # ASS 헤더
    ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
Collisions: Normal

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Noto Sans CJK KR,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,60,60,120,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    for i, sent in enumerate(sentences):
        start = i * dur_per
        end   = (i + 1) * dur_per - 0.1
        # 줄 길이 제한 (한 줄 최대 15자)
        if len(sent) > 15:
            mid = len(sent) // 2
            sent = sent[:mid] + '\\N' + sent[mid:]
        ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0,0,0,,{sent}\n"

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)

    print(f"  자막 {len(sentences)}개 문장 생성 완료 (ASS 형식)")
    return path

# =============================================
# 6단계: 최종 영상 합성
# =============================================
def final_render(clips, ass_path):
    print("\n[5/5] 최종 영상 합성 중...")

    # 클립 연결
    concat_file = 'temp/concat.txt'
    with open(concat_file, 'w') as f:
        for clip in clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    r = run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
             '-c', 'copy', 'temp/merged.mp4', '-y'])
    if not Path('temp/merged.mp4').exists():
        print("  클립 연결 실패")
        raise Exception("merged.mp4 생성 실패")

    print("  클립 연결 완료")

    # 자막 경로 (절대경로)
    abs_ass = os.path.abspath(ass_path).replace('\\', '/').replace(':', '\\:')

    # 최종 합성: 자막 + 음성
    r = run([
        'ffmpeg',
        '-i', 'temp/merged.mp4',
        '-i', 'temp/audio.mp3',
        '-vf', f"ass={abs_ass}",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        'output/final.mp4', '-y'
    ])

    if not Path('output/final.mp4').exists():
        print("  자막 합성 실패 — 자막 없이 재시도")
        # 자막 없이 재시도 (폴백)
        r2 = run([
            'ffmpeg',
            '-i', 'temp/merged.mp4',
            '-i', 'temp/audio.mp3',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
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
        narration, duration = generate_tts()
        sources  = download_sources()
        clips    = build_clips(sources, duration)
        ass_path = build_subtitles_ass(narration, duration)
        final_render(clips, ass_path)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
