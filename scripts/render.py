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
# 0단계: 폰트 설치
# =============================================
def install_fonts():
    print("\n[0/6] 한국어 폰트 설치 중...")
    run(['sudo', 'apt-get', 'update', '-qq'])
    run(['sudo', 'apt-get', 'install', '-y', '--fix-missing', 'fonts-noto-cjk'])
    run(['fc-cache', '-fv'])
    print("  폰트 설치 완료")

# =============================================
# 1단계: Gemini 이미지 생성 (구간별)
# =============================================
def generate_gemini_images():
    print("\n[1/6] Gemini AI 이미지 생성 중...")
    is_wow  = SCRIPT_DATA.get('type') == 'wow'
    product = SCRIPT_DATA.get('product', '')

    # 구간별 프롬프트 — 상품에 특화된 구체적 장면
    if is_wow:
        prompts = {
            'opening':  f'Extreme close-up mysterious shot of {product}, black background, dramatic neon lighting, cinematic, ultra high contrast, no text, no people',
            'proof':    f'{product} product detail shot, white studio background, professional lighting, sharp focus, no text',
            'usage':    f'Person happily using {product} in daily life, warm natural light, lifestyle photography, Korean person, no text',
            'cta':      f'{product} on minimal dark background, spotlight lighting, premium feel, no text',
        }
    else:
        prompts = {
            'opening':  f'Korean person looking frustrated or stressed about problem that {product} solves, dramatic lighting, cinematic portrait, emotional expression, no text',
            'empathy':  f'Close-up of the specific problem situation that {product} solves, messy or uncomfortable scene, realistic, no text',
            'solution': f'Korean person smiling while using {product}, clean bright background, before-after feel, satisfied expression, no text',
            'cta':      f'{product} product shot on dark background with spotlight, premium minimal style, no text',
        }

    images = {}
    section_keys = list(prompts.keys())

    for key in section_keys:
        # 웹앱에서 선택한 소스가 있으면 우선 사용
        source   = SOURCES_DATA.get(key, {})
        selected = source.get('selected')

        if selected and selected.get('data', {}).get('url') and selected.get('idx') != 'ai':
            # Pexels 영상 선택됨 — 다운로드
            url  = selected['data']['url']
            path = f'temp/src_{key}.mp4'
            print(f"  [{key}] 선택된 Pexels 영상 다운로드...")
            try:
                r = requests.get(url, timeout=60, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                images[key] = {'type': 'video', 'path': path}
                print(f"  [{key}] 다운로드 완료")
                continue
            except Exception as e:
                print(f"  [{key}] 다운로드 실패: {e}")

        # Gemini 이미지 생성 (기본 + AI 선택 시)
        print(f"  [{key}] Gemini 이미지 생성: {prompts[key][:60]}...")
        try:
            res = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={GEMINI_KEY}',
                json={
                    'contents': [{'parts': [{'text': prompts[key]}]}],
                    'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}
                },
                timeout=40
            )
            parts = res.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
            img_part = next((p for p in parts if 'inlineData' in p), None)
            if img_part:
                path = f'temp/ai_{key}.jpg'
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(img_part['inlineData']['data']))
                images[key] = {'type': 'image', 'path': path}
                print(f"  [{key}] Gemini 이미지 생성 완료")
            else:
                print(f"  [{key}] Gemini 응답 없음 — 검정 배경 사용")
                images[key] = {'type': 'color'}
        except Exception as e:
            print(f"  [{key}] 이미지 생성 실패: {e}")
            images[key] = {'type': 'color'}

    return images

# =============================================
# 2단계: TTS 음성 생성 (타임포인트)
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

        # 타임포인트 추출
        timepoints = {}
        for tp in data.get('timepoints', []):
            mark = tp.get('markName', '')
            if mark.startswith('s'):
                timepoints[int(mark[1:])] = tp.get('timeSeconds', 0)

        result = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'default=noprint_wrappers=1:nokey=1', 'temp/audio.mp3'])
        duration = float(result.stdout.strip() or '25')
        print(f"  TTS 완료: {duration:.1f}초, 타임포인트: {timepoints}")
        return sentences, narration, duration, timepoints

    except Exception as e:
        print(f"  TTS 실패: {e}")
        run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '25', '-q:a', '9', '-acodec', 'libmp3lame', 'temp/audio.mp3', '-y'])
        timepoints = {i: i * (25 / max(len(sentences), 1)) for i in range(len(sentences))}
        return sentences, narration, 25.0, timepoints

# =============================================
# 3단계: 구간별 클립 생성
# =============================================
def make_clip(source, duration, output_path, speed=1.0):
    w, h     = 1080, 1920
    duration = max(duration, 0.5)
    vf_base  = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray'

    if source['type'] == 'video' and source.get('path') and Path(source['path']).exists():
        pts = f'setpts={1/speed:.4f}*PTS'
        cmd = ['ffmpeg', '-i', source['path'],
               '-vf', f'{vf_base},{pts}',
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']
    elif source['type'] == 'image' and source.get('path') and Path(source['path']).exists():
        # 이미지 — 줌인 효과 추가 (더 역동적)
        zoom = f'zoompan=z=\'min(zoom+0.001,1.3)\':d={int(duration*30)}:s={w}x{h}'
        cmd = ['ffmpeg', '-loop', '1', '-i', source['path'],
               '-vf', f'scale={w*2}:{h*2},{zoom},format=gray',
               '-t', str(duration), '-r', '30',
               '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']
    else:
        cmd = ['ffmpeg', '-f', 'lavfi',
               '-i', f'color=black:size={w}x{h}:rate=30',
               '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast', '-an',
               output_path, '-y']

    run(cmd)
    # 실패 시 단순 이미지로 재시도
    if not Path(output_path).exists() and source['type'] == 'image':
        cmd2 = ['ffmpeg', '-loop', '1', '-i', source['path'],
                '-vf', vf_base,
                '-t', str(duration), '-r', '30',
                '-c:v', 'libx264', '-preset', 'fast', '-an',
                output_path, '-y']
        run(cmd2)

def build_clips(sources, total_duration, timepoints, sentences):
    print("\n[3/6] 구간별 클립 생성 중...")
    is_wow = SCRIPT_DATA.get('type') == 'wow'

    if is_wow:
        section_keys = ['opening', 'proof', 'usage', 'cta']
        speeds       = {'opening': 1.2, 'proof': 0.8, 'usage': 1.05, 'cta': 1.0}
    else:
        section_keys = ['opening', 'empathy', 'solution', 'cta']
        speeds       = {'opening': 1.15, 'empathy': 1.0, 'solution': 1.0, 'cta': 1.0}

    durations = {}
    for i, key in enumerate(section_keys):
        start = timepoints.get(i, i * total_duration / len(section_keys))
        end   = timepoints.get(i+1, start + total_duration / len(section_keys)) if i+1 < len(section_keys) else total_duration
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
# 4단계: 오프닝 강렬한 텍스트 오버레이
# =============================================
def add_opening_text_overlay(clip_path, opening_text, duration):
    """첫 장면에 대형 후킹 텍스트 오버레이 추가"""
    print("\n[4/6] 오프닝 텍스트 오버레이 추가 중...")
    output_path = 'temp/clip_opening_final.mp4'

    # 텍스트 줄바꿈 (15자 기준)
    text = opening_text.replace("'", "\\'").replace('"', '\\"').replace(':', '\\:')
    if len(opening_text) > 15:
        mid = len(opening_text) // 2
        text = opening_text[:mid].replace("'", "\\'") + '\\n' + opening_text[mid:].replace("'", "\\'")

    # 대형 중앙 텍스트 + 노란 강조
    drawtext = (
        f"drawtext=fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        f":text='{text}'"
        f":fontsize=90"
        f":fontcolor=yellow"
        f":borderw=4"
        f":bordercolor=black"
        f":x=(w-text_w)/2"
        f":y=(h-text_h)/2"
        f":enable='between(t,0.3,{duration})'"
    )

    result = run([
        'ffmpeg', '-i', clip_path,
        '-vf', drawtext,
        '-c:v', 'libx264', '-preset', 'fast', '-an',
        output_path, '-y'
    ])

    if Path(output_path).exists():
        print("  오프닝 텍스트 오버레이 완료")
        return output_path
    else:
        print("  오프닝 텍스트 실패 — 원본 사용")
        return clip_path

# =============================================
# 5단계: 자막 생성 (대형 중앙 ASS)
# =============================================
def build_subtitles_ass(sentences, total_duration, timepoints):
    print("\n[5/6] 자막 파일 생성 중...")

    def fmt(t):
        t  = max(0, t)
        h  = int(t // 3600)
        m  = int((t % 3600) // 60)
        s  = int(t % 60)
        cs = int((t % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # 대형 중앙 자막 스타일
    # - 폰트 크기 90 (기존 72 → 대폭 확대)
    # - 화면 하단 1/3 위치
    # - 흰색 + 검정 외곽선 4px + 반투명 검정 배경박스
    # - Bold
    ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Noto Sans CJK KR,90,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,2,0,3,5,3,2,60,60,200,1
Style: Highlight,Noto Sans CJK KR,90,&H00FFD600,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,2,0,3,5,3,2,60,60,200,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    for i, sent in enumerate(sentences):
        start = timepoints.get(i, i * (total_duration / len(sentences)))
        end   = (timepoints.get(i+1, start + total_duration / len(sentences)) - 0.05) if i+1 < len(sentences) else (total_duration - 0.05)

        # 첫 문장(오프닝)은 노란색 강조 스타일
        style = 'Highlight' if i == 0 else 'Default'

        # 줄바꿈 (14자 기준)
        if len(sent) > 14:
            mid  = len(sent) // 2
            sent = sent[:mid] + '\\N' + sent[mid:]

        ass += f"Dialogue: 0,{fmt(start)},{fmt(end)},{style},,0,0,0,,{sent}\n"

    path = 'temp/subtitles.ass'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ass)

    print(f"  자막 {len(sentences)}개 생성 완료 (대형 중앙 스타일)")
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
        sources                                      = generate_gemini_images()
        sentences, narration, duration, timepoints   = generate_tts()
        clips                                        = build_clips(sources, duration, timepoints, sentences)

        # 오프닝 텍스트 오버레이
        opening_text = SCRIPT_DATA.get('opening', '')
        if clips and opening_text:
            clips[0] = add_opening_text_overlay(clips[0], opening_text, duration)

        ass_path = build_subtitles_ass(sentences, duration, timepoints)
        final_render(clips, ass_path)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
