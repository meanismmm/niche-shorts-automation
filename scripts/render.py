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

print("=== 니치 쇼츠 자동 렌더링 시작 ===")
print(f"상품: {SCRIPT_DATA.get('product', '알 수 없음')}")
print(f"유형: {SCRIPT_DATA.get('type', '알 수 없음')}")

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
# 0단계: 한국어 폰트 설치
# =============================================
def install_fonts():
    print("\n[0/6] 한국어 폰트 설치 중...")
    run(['sudo', 'apt-get', 'update', '-qq'])
    run(['sudo', 'apt-get', 'install', '-y', '--fix-missing', 'fonts-noto-cjk'])
    run(['fc-cache', '-fv'])
    print("  폰트 설치 완료")

# =============================================
# 1단계: Claude로 Pexels 키워드 생성
# =============================================
def generate_pexels_keywords():
    print("\n[1/6] Pexels 검색 키워드 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'
    product = SCRIPT_DATA.get('product', '')

    if is_wow:
        sections = ['opening', 'proof', 'usage', 'cta']
        texts = {
            'opening': SCRIPT_DATA.get('opening', ''),
            'proof':   SCRIPT_DATA.get('proof', ''),
            'usage':   SCRIPT_DATA.get('usage', ''),
            'cta':     SCRIPT_DATA.get('cta', ''),
        }
    else:
        sections = ['opening', 'empathy', 'solution', 'cta']
        texts = {
            'opening':  SCRIPT_DATA.get('opening', ''),
            'empathy':  SCRIPT_DATA.get('empathy', ''),
            'solution': SCRIPT_DATA.get('solution', ''),
            'cta':      SCRIPT_DATA.get('cta', ''),
        }

    prompt = f"""You are a Pexels video search expert.
Product: {product}
Type: {'WOW' if is_wow else 'PAIN'}

For each section below, generate the BEST English Pexels search keyword (2-4 words max).
The keyword must find videos that EXACTLY match the scene described.
Return ONLY valid JSON, no other text.

Sections and their script content:
{json.dumps(texts, ensure_ascii=False)}

Return format:
{{"opening": "keyword", {'"proof"' if is_wow else '"empathy"'}: "keyword", {'"usage"' if is_wow else '"solution"'}: "keyword", "cta": "keyword"}}"""

    try:
        res = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': CLAUDE_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 200,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=20
        )
        text = res.json()['content'][0]['text'].strip()
        keywords = json.loads(text)
        print(f"  키워드 생성 완료: {keywords}")
        return keywords
    except Exception as e:
        print(f"  키워드 생성 실패: {e}, 기본값 사용")
        return {s: product for s in sections}

# =============================================
# 2단계: TTS 음성 생성 (타임포인트 포함)
# =============================================
def generate_tts():
    print("\n[2/6] TTS 음성 생성 중...")
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

    sentences = [convert_units(s) for s in sentences if s.strip()]
    narration = ' '.join(sentences)

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

    # SSML로 문장별 마크 삽입 (타임포인트용)
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

        # 타임포인트 추출
        timepoints = {}
        for tp in data.get('timepoints', []):
            mark = tp.get('markName', '')
            time_sec = tp.get('timeSeconds', 0)
            if mark.startswith('s'):
                idx = int(mark[1:])
                timepoints[idx] = time_sec

        # 음성 총 길이
        result = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'])
        duration = float(result.stdout.strip() or '25')

        print(f"  음성 생성 완료: {duration:.1f}초, 타임포인트: {timepoints}")
        return sentences, narration, duration, timepoints

    except Exception as e:
        print(f"  TTS 실패: {e}, 무음 사용")
        run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '25', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        timepoints = {i: i * 5 for i in range(len(sentences))}
        return sentences, narration, 25.0, timepoints

# =============================================
# 3단계: 소스 다운로드 (개선된 키워드 사용)
# =============================================
def search_pexels(keyword, per_page=3):
    try:
        res = requests.get(
            f'https://api.pexels.com/videos/search?query={requests.utils.quote(keyword)}&per_page={per_page}&orientation=portrait',
            headers={'Authorization': PEXELS_KEY}, timeout=15
        )
        videos = res.json().get('videos', [])
        for v in videos:
            url = next((f['link'] for f in v.get('video_files', []) if f.get('quality') == 'sd'), None)
            if not url and v.get('video_files'):
                url = v['video_files'][0]['link']
            if url:
                return url
        return None
    except:
        return None

def generate_ai_image(prompt):
    try:
        res = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={GEMINI_KEY}',
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}
            },
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

def download_sources(keywords):
    print("\n[3/6] 소스 다운로드 중...")
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
                'opening':  f'dramatic cinematic scene, person without {product}, frustrated daily life, dark moody, no text',
                'solution': f'{product} being used by happy person, warm natural lighting, lifestyle, no text',
                'proof':    f'close-up detail shot of {product}, studio lighting, product photography, no text',
                'empathy':  f'person looking concerned or frustrated, cinematic lighting, no text',
            }
            img = generate_ai_image(prompts.get(key, f'{product} product photography, no text'))
            downloaded[key] = {'type': 'image', 'path': img} if img else {'type': 'color'}

        elif selected and selected.get('data', {}).get('url'):
            url = selected['data']['url']
            print(f"  [{key}] 선택된 Pexels 영상 다운로드 중...")
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
            # Claude가 생성한 키워드로 자동 검색
            kw = keywords.get(key, product)
            print(f"  [{key}] 자동 검색: '{kw}'")
            url = search_pexels(kw)
            if url:
                path = f'temp/src_{key}.mp4'
                r = requests.get(url, timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded[key] = {'type': 'video', 'path': path}
                print(f"  [{key}] 완료")
            else:
                downloaded[key] = {'type': 'color'}

    return downloaded

# =============================================
# 4단계: 구간별 클립 생성
# =============================================
def make_clip(source, duration, output_path, speed=1.0):
    w, h = 1080, 1920
    vf_base = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray'
    duration = max(duration, 0.5)

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

def build_clips(sources, total_duration, timepoints, sentences):
    print("\n[4/6] 구간별 클립 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    if is_wow:
        section_keys = ['opening', 'proof', 'usage', 'cta']
        speeds = {'opening': 1.2, 'proof': 0.8, 'usage': 1.05, 'cta': 1.0}
    else:
        section_keys = ['opening', 'empathy', 'solution', 'cta']
        speeds = {'opening': 1.15, 'empathy': 1.0, 'solution': 1.0, 'cta': 1.0}

    # 타임포인트 기반 구간 길이 계산
    durations = {}
    for i, key in enumerate(section_keys):
        start = timepoints.get(i, i * (total_duration / len(section_keys)))
        if i + 1 < len(section_keys):
            end = timepoints.get(i + 1, start + total_duration / len(section_keys))
        else:
            end = total_duration
        durations[key] = max(end - start, 0.5)

    clips = []
    for key in section_keys:
        dur = durations[key]
        src = sources.get(key, {'type': 'color'})
        out = f'temp/clip_{key}.mp4'
        make_clip(src, dur, out, speeds.get(key, 1.0))
        if Path(out).exists():
            clips.append(out)
            print(f"  [{key}] {dur:.1f}초 완료")
        else:
            print(f"  [{key}] 실패 — 검정 배경 대체")
            make_clip({'type': 'color'}, dur, out)
            if Path(out).exists():
                clips.append(out)

    return clips

# =============================================
# 5단계: 자막 생성 (타임포인트 싱크)
# =============================================
def build_subtitles_ass(sentences, total_duration, timepoints):
    print("\n[5/6] 자막 파일 생성 중...")

    def fmt(t):
        t = max(0, t)
        h  = int(t // 3600)
        m  = int((t % 3600) // 60)
        s  = int(t % 60)
        cs = int((t % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Noto Sans CJK KR,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,60,60,120,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    for i, sent in enumerate(sentences):
        start = timepoints.get(i, i * (total_duration / len(sentences)))
        if i + 1 < len(sentences):
            end = timepoints.get(i + 1, start + total_duration / len(sentences)) - 0.05
        else:
            end = total_duration - 0.05

        # 긴 문장 줄바꿈
        if len(sent) > 16:
            mid = len(sent) // 2
            sent = sent[:mid] + '\\N' + sent[mid:]

        ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0,0,0,,{sent}\n"

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)

    print(f"  자막 {len(sentences)}개 (타임포인트 싱크 적용)")
    return path

# =============================================
# 6단계: 최종 합성
# =============================================
def final_render(clips, ass_path):
    print("\n[6/6] 최종 영상 합성 중...")

    concat_file = 'temp/concat.txt'
    with open(concat_file, 'w') as f:
        for clip in clips:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
         '-c', 'copy', 'temp/merged.mp4', '-y'])

    if not Path('temp/merged.mp4').exists():
        raise Exception("클립 연결 실패")

    print("  클립 연결 완료")

    abs_ass = os.path.abspath(ass_path).replace('\\', '/').replace(':', '\\:')

    # 자막 + 음성 합성
    r = run([
        'ffmpeg',
        '-i', 'temp/merged.mp4',
        '-i', 'temp/audio.mp3',
        '-vf', f"ass='{abs_ass}'",
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
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
        keywords              = generate_pexels_keywords()
        sentences, narration, duration, timepoints = generate_tts()
        sources               = download_sources(keywords)
        clips                 = build_clips(sources, duration, timepoints, sentences)
        ass_path              = build_subtitles_ass(sentences, duration, timepoints)
        final_render(clips, ass_path)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
