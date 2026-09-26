import base64
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import uuid

FFMPEG = os.environ.get('FFMPEG_PATH', 'ffmpeg')


def run(args):
    p = subprocess.run([FFMPEG, '-hide_banner', '-nostdin', '-y', *map(str, args)], capture_output=True, timeout=1800)
    if p.returncode:
        raise ValueError('视频处理失败：' + p.stderr.decode(errors='replace')[-700:])
    return p


def probe(path):
    p = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path)], capture_output=True, timeout=30)
    info = p.stderr.decode(errors='replace')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', info)
    if not m or 'Video:' not in info:
        raise ValueError('无法读取视频，请使用 MOV 或 MP4 文件')
    duration = int(m[1])*3600 + int(m[2])*60 + float(m[3])
    if duration <= 0 or duration > 7200:
        raise ValueError('第一版支持两小时以内的视频')
    return duration


def orientation(turns):
    return {0: '', 1: 'transpose=clock,', 2: 'hflip,vflip,', 3: 'transpose=cclock,'}[turns]


def normalize(source, target, turns):
    info = subprocess.run([FFMPEG,'-hide_banner','-i',str(source)],capture_output=True,timeout=30).stderr.decode(errors='replace')
    tone = 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,' if any(v in info for v in ('arib-std-b67','smpte2084')) else ''
    run(['-i', source, '-vf', orientation(turns)+tone+'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p',
         '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-ac', '2', '-movflags', '+faststart', target])


def analyze(source, duration, player, progress):
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        raise ValueError('云端尚未配置 AI 服务；仍可手动标记出手和生成集锦')
    candidates = []
    with tempfile.TemporaryDirectory() as temp:
        for chunk in range(math.ceil(duration/20)):
            start = chunk*20
            folder = Path(temp)/str(chunk)
            folder.mkdir()
            run(['-ss', start, '-i', source, '-t', min(22, duration-start), '-vf', 'fps=2,scale=640:-2', '-q:v', '5', folder/'%04d.jpg'])
            content = [{'type': 'input_text', 'text': f'分析篮球训练连续画面。只找球员：{player}。所有画面时间均为整段视频的秒数。找出实际出手，不包含传球、其他球员或重复动作。对无法确定球员身份的动作不要猜测。每条返回 start/release/end (秒), outcome (made/missed/unknown), note (中文可见证据及不确定性)。球路看不清或多人重叠时 outcome 必须 unknown。仅报告 release 位于 [{start},{min(start+20,duration)}) 的出手。每个片段 start>=0，end<={duration}。'}]
            for i, frame in enumerate(sorted(folder.glob('*.jpg'))):
                content.extend([{'type': 'input_text', 'text': f'{start+i*.5:.1f} 秒'},
                                {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,'+base64.b64encode(frame.read_bytes()).decode(), 'detail': 'auto'}])
            shot_schema = dict(type='object', properties={
                'start': {'type':'number'}, 'release': {'type':'number'}, 'end': {'type':'number'},
                'outcome': {'type':'string','enum':['made','missed','unknown']}, 'note': {'type':'string'}},
                required=['start','release','end','outcome','note'], additionalProperties=False)
            payload = dict(model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'), store=False,
                           input=[dict(role='user',content=content)],
                           text={'format':dict(type='json_schema', name='shots', strict=True,
                                 schema=dict(type='object',properties={'shots':dict(type='array',items=shot_schema)}, required=['shots'],additionalProperties=False))})
            req = urllib.request.Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(), headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=180) as response:
                    data = json.load(response)
            except Exception as exc:
                raise ValueError('AI 请求失败，请检查服务密钥、额度或网络；可稍后重试') from exc
            result = ''.join(c.get('text','') for item in data.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text')
            try:
                entries = json.loads(result)['shots']
                for shot in entries:
                    release = float(shot['release'])
                    a, b = float(shot['start']), float(shot['end'])
                    if not all(math.isfinite(v) for v in (a,b,release)) or not start <= release < min(start+20,duration):
                        continue
                    a, b = max(0,min(a,release)), min(duration,max(b,release+.1))
                    if b <= release or any(abs(s['release']-release)<1.5 for s in candidates):
                        continue
                    if shot['outcome'] not in ('made','missed','unknown'):
                        continue
                    candidates.append(dict(id=str(uuid.uuid4()),start=a,release=release,end=b,outcome=shot['outcome'],reviewed=False,note=str(shot['note'])[:2000]))
            except (ValueError,KeyError,TypeError) as exc:
                raise ValueError('AI 未返回有效投篮记录，请重试或手动记录') from exc
            progress(f'正在识别 {min(start+20,duration):.0f} / {duration:.0f} 秒')
    return candidates


def highlight(source, target, shots, stats, progress):
    made = [s for s in shots if s['reviewed'] and s['outcome']=='made']
    if not made:
        raise ValueError('请先确认至少一个进球')
    with tempfile.TemporaryDirectory() as temp:
        clips=[]
        segments=[(s,1) for s in made]+[(s,2) for s in made[:3]]
        for i,(shot,slow) in enumerate(segments):
            progress(f'正在剪辑 {i+1} / {len(segments)}')
            path=Path(temp)/f'{i:04}.mp4'
            # Silent slow-motion avoids stretched speech; original video is preserved.
            run(['-ss',shot['start'],'-t',shot['end']-shot['start'],'-i',source,
                 '-vf',f'setpts={slow}*(PTS-STARTPTS),fps=30,format=yuv420p', '-an',
                 '-c:v','libx264','-preset','veryfast','-crf','22',path])
            clips.append(path)
        # An actual recap card is included in the exported file.
        from PIL import Image,ImageDraw,ImageFont
        font_path=os.environ.get('FONT_PATH','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
        card=Image.new('RGB',(1280,720),'#101828')
        draw=ImageDraw.Draw(card)
        title=ImageFont.truetype(font_path,52)
        body=ImageFont.truetype(font_path,32)
        draw.text((80,100),'2 号球员训练记录与复盘',font=title,fill='#ffffff')
        draw.text((80,225),f"已核对 {stats['attempts']} 次出手  /  命中 {stats['made']} 次  /  {stats['percentage']:.1f}%",font=body,fill='#ff9c55')
        draw.text((80,325),'仅统计这段录像中已确认的出手',font=body,fill='#b6c2d2')
        draw.text((80,400),'下次重点：固定准备脚步，分组记录每球结果。',font=body,fill='white')
        draw.text((80,470),'动作不足请结合原片核对，不能仅凭命中率判断。',font=body,fill='#b6c2d2')
        card.save(Path(temp)/'recap.png')
        end=Path(temp)/'recap.mp4'
        run(['-loop','1','-i',Path(temp)/'recap.png','-t','5','-vf','fps=30,format=yuv420p','-an','-c:v','libx264',end])
        clips.append(end)
        listing=Path(temp)/'clips.txt'
        listing.write_text('\n'.join(f"file '{p.name}'" for p in clips))
        run(['-f','concat','-safe','0','-i',listing,'-c','copy','-movflags','+faststart',target])
