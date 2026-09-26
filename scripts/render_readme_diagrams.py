"""Render portable README diagrams without a browser or external dependencies."""
from pathlib import Path
from html import escape

OUT=Path(__file__).resolve().parents[1]/'docs/images'
OUT.mkdir(parents=True,exist_ok=True)

def canvas(title,desc,height):
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0 1 L8 5 L0 9" fill="none" stroke="#8794a8" stroke-width="1.5"/></marker></defs>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC","Microsoft YaHei",sans-serif}} .label{{font-size:19px;font-weight:650;fill:#172b44}} .detail{{font-size:14px;fill:#52657c}} .line{{fill:none;stroke:#8794a8;stroke-width:2;marker-end:url(#arrow)}}</style>
<rect width="960" height="{height}" rx="20" fill="#f5f7fa"/>
<text x="32" y="42" font-size="21" font-weight="700" fill="#172b44">{escape(title)}</text>''']

def card(parts,x,y,w,h,title,detail,accent=False):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{"#fff1e5" if accent else "white"}" stroke="{"#f6a457" if accent else "#d8e0eb"}"/>')
    parts.append(f'<text x="{x+w/2}" y="{y+33}" text-anchor="middle" class="label">{escape(title)}</text>')
    parts.append(f'<text x="{x+w/2}" y="{y+58}" text-anchor="middle" class="detail">{escape(detail)}</text>')

def line(parts,d): parts.append(f'<path d="{d}" class="line"/>')

def write(parts,name): (OUT/name).write_text('\n'.join(parts+['</svg>']))

p=canvas('从一段视频，到下一次训练','手机上传视频，准备预览，手动或 AI 辅助记录出手，经人工核对后生成统计、集锦与训练计划。',380)
xs=[28,212,396,580,764]
for x in xs[:-1]: line(p,f'M{x+164} 136 H{x+182}')
for x,title,detail,accent in zip(xs,['手机上传','视频准备','记录出手','逐球核对','确认统计'],['选取相册视频','方向与格式处理','手动 / 可选 AI','命中或未命中','明确结果才计入'],[True,False,False,False,True]):
    card(p,x,94,164,84,title,detail,accent)
line(p,'M846 178 V220 H316 V248')
line(p,'M846 220 H664 V248')
card(p,188,252,256,84,'复盘与下次计划','带着练习重点开始下一次训练')
card(p,536,252,256,84,'进球集锦与分享','正常速度 · 慢动作 · 复盘尾卡')
p.append('<text x="32" y="362" class="detail">AI 候选先核对；未知结果不算未命中；重播不增加出手数。</text>')
write(p,'training-flow.svg')

p=canvas('手机负责记录，服务负责处理','iPhone 连接个人训练服务，服务使用 FFmpeg 处理视频，选择性调用视觉 AI，并持久保存训练数据和媒体。',420)
line(p,'M220 226 H318')
line(p,'M540 226 H592 V111 H660')
line(p,'M592 226 H660')
line(p,'M592 226 V341 H660')
card(p,32,184,188,84,'iPhone App','相册 · 回看 · 核对',True)
card(p,322,184,218,84,'个人训练服务','接收视频 · 组织任务',True)
card(p,664,69,264,84,'FFmpeg 视频处理','方向调整 · 转码 · 剪辑')
card(p,664,184,264,84,'可选视觉 AI','确认发送画面后生成候选')
card(p,664,299,264,84,'持久保存','SQLite 记录 + 视频文件')
p.append('<text x="32" y="396" class="detail">云端部署完成后，上传后的任务不依赖 Mac 开机。</text>')
write(p,'project-architecture.svg')
