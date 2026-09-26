"""Personal, token-authenticated API. Put behind HTTPS for iPhone/cloud use."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import ssl
import threading
import uuid
from urllib.parse import urlparse, parse_qs

from server.domain import validate_shots, statistics, report
from server import media

DATA = Path(os.environ.get('DATA_DIR', './data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get('APP_TOKEN', '')
if not TOKEN:
    secret = DATA / '.token'
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(32))
        secret.chmod(0o600)
    TOKEN = secret.read_text().strip()
    print('Local API token: stored in data/.token (not printed).', flush=True)
DB = DATA / 'journal.sqlite3'
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)


@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=20)
    db.execute('PRAGMA journal_mode=WAL')
    try:
        with db:
            yield db
    finally:
        db.close()


with connection() as db:
    db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
    # Incomplete jobs fail explicitly after a process restart; users can retry safely.
    for ident, raw in db.execute('SELECT id, document FROM sessions').fetchall():
        doc=json.loads(raw)
        if doc['busy']:
            doc.update(busy=False,status='任务中断，可重新处理',error='服务重启，请重试相应操作')
            db.execute('UPDATE sessions SET document=? WHERE id=?',(json.dumps(doc),ident))


def save(doc):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)',(doc['id'],json.dumps(doc,ensure_ascii=False)))


def get(ident):
    with connection() as db:
        row=db.execute('SELECT document FROM sessions WHERE id=?',(ident,)).fetchone()
    if not row:
        raise FileNotFoundError('训练记录不存在')
    return json.loads(row[0])


def present(doc):
    return dict(doc,stats=statistics(doc['shots']),report=report(doc),aiAvailable=bool(os.environ.get('OPENAI_API_KEY')),
                previewReady=(DATA/doc['id']/'preview.mp4').exists(),
                highlightReady=(DATA/doc['id']/'highlight.mp4').exists(),
                highlightStale=doc.get('exportRevision',-1)!=doc['revision'])


def update(ident, **values):
    with LOCK:
        doc=get(ident)
        doc.update(values)
        save(doc)


def job(ident, kind):
    folder=DATA/ident
    try:
        doc=get(ident)
        progress=lambda status:update(ident,status=status)
        if kind=='prepare':
            tmp=folder/'preview.new.mp4'
            media.normalize(folder/'source.mov',tmp,doc['turns'])
            tmp.replace(folder/'preview.mp4')
        elif kind=='analyze':
            shots=media.analyze(folder/'preview.mp4',doc['duration'],doc['player'],progress)
            # Do not overwrite reviewed or manually recorded shots on retry.
            existing=doc['shots']
            shots=[s for s in shots if not any(abs(s['release']-e['release'])<1.5 for e in existing)]
            update(ident,shots=validate_shots(existing+shots,doc['duration']),revision=doc['revision']+1)
        elif kind=='render':
            tmp=folder/'highlight.new.mp4'
            media.highlight(folder/'preview.mp4',tmp,doc['shots'],statistics(doc['shots']),progress)
            tmp.replace(folder/'highlight.mp4')
            update(ident,exportRevision=doc['revision'])
        update(ident,busy=False,status='可以核对出手' if kind!='render' else '集锦已完成',error='')
    except Exception as exc:
        update(ident,busy=False,status='处理失败，可重试',error=str(exc)[:1000])


def launch(ident,kind):
    with LOCK:
        doc=get(ident)
        if doc['busy']:
            raise ValueError('正在处理，请稍后再试')
        if kind!='prepare' and not (DATA/ident/'preview.mp4').exists():
            raise ValueError('请先完成视频准备')
        if kind=='analyze' and not os.environ.get('OPENAI_API_KEY'):
            raise ValueError('云端未配置 AI 服务，仍可手动记录')
        if kind=='render' and statistics(doc['shots'])['made']==0:
            raise ValueError('请先确认至少一个进球')
        doc.update(busy=True,status='任务已排队',error='')
        save(doc)
        POOL.submit(job,ident,kind)


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'

    def log_message(self,fmt,*args):
        # Never log authorization headers or original video titles.
        pass

    def respond(self,value,status=200):
        if os.environ.get('LOCAL_ACCESS_LOG')=='1':
            # Only connection diagnostics: no URLs, video titles, tokens or bodies.
            print(f'API {self.command} {status} client={self.client_address[0]}',flush=True)
        payload=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(payload)

    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0<=size<=1_000_000:
            raise ValueError('请求过大')
        return json.loads(self.rfile.read(size) or b'{}')

    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def do_HEAD(self): self.handle_request()

    def handle_request(self):
        self.connection.settimeout(120)
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN):
            self.close_connection=True
            self.respond({'error':'请检查服务地址和访问令牌'},401)
            return
        try:
            self.route()
        except FileNotFoundError as exc:
            self.respond({'error':str(exc)},404)
        except (ValueError,KeyError,TypeError) as exc:
            self.close_connection=True
            self.respond({'error':str(exc)},400)
        except (BrokenPipeError,ConnectionResetError):
            self.close_connection=True
        except Exception:
            self.close_connection=True
            self.respond({'error':'服务器处理失败，请稍后重试'},500)

    def route(self):
        parsed=urlparse(self.path)
        path=parsed.path
        if path=='/api/sessions' and self.command=='GET':
            with connection() as db:
                docs=[present(json.loads(r[0])) for r in db.execute('SELECT document FROM sessions ORDER BY rowid DESC')]
            self.respond(docs)
            return
        if path=='/api/upload' and self.command=='POST':
            self.upload(parse_qs(parsed.query))
            return
        match=re.fullmatch(r'/api/sessions/([a-f0-9-]{36})(?:/(analyze|render|prepare|rotate|preview|highlight))?',path)
        if not match:
            raise FileNotFoundError('接口不存在')
        ident,action=match.groups()
        doc=get(ident)
        if self.command in ('GET','HEAD') and action in ('preview','highlight'):
            self.stream(DATA/ident/(action+'.mp4'))
        elif self.command=='GET' and not action:
            self.respond(present(doc))
        elif self.command=='PUT' and not action:
            data=self.body()
            with LOCK:
                doc=get(ident)
                if doc['busy']:
                    raise ValueError('处理期间请稍后再修改')
                if data.get('revision')!=doc['revision']:
                    self.respond({'error':'记录已更新，请刷新后重试'},409)
                    return
                doc.update(shots=validate_shots(data['shots'],doc['duration']),revision=doc['revision']+1)
                save(doc)
            self.respond(present(doc))
        elif self.command=='POST' and action in ('analyze','render','prepare','rotate'):
            self.body()
            if action=='rotate':
                with LOCK:
                    doc=get(ident)
                    if doc['busy']:
                        raise ValueError('处理期间请稍后再修改')
                    doc.update(turns=(doc['turns']+1)%4,revision=doc['revision']+1)
                    save(doc)
                    launch(ident,'prepare')
            else:
                launch(ident,action)
            self.respond(present(get(ident)),202)
        else:
            raise FileNotFoundError('接口不存在')

    def upload(self,query):
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=2*1024**3:
            raise ValueError('请选择 2 GB 以内的视频')
        training_date=query.get('date',[date.today().isoformat()])[0]
        date.fromisoformat(training_date)
        title=query.get('title',['篮球训练'])[0].strip()[:120] or '篮球训练'
        player=query.get('player',['蓝色 2 号球衣，白色短裤'])[0].strip()[:200]
        ident=str(uuid.uuid4())
        folder=DATA/ident
        folder.mkdir()
        file=folder/'source.mov'
        try:
            remaining=size
            with file.open('wb') as target:
                while remaining:
                    chunk=self.rfile.read(min(1024*1024,remaining))
                    if not chunk:
                        raise ValueError('上传中断，请重新选择视频')
                    target.write(chunk)
                    remaining-=len(chunk)
            duration=media.probe(file)
        except Exception:
            file.unlink(missing_ok=True)
            folder.rmdir()
            raise
        doc=dict(id=ident,title=title,date=training_date,player=player,duration=duration,
                 shots=[],revision=0,turns=0,busy=False,status='视频已上传',error='')
        save(doc)
        launch(ident,'prepare')
        self.respond(present(get(ident)),201)

    def stream(self,path):
        if not path.exists():
            raise FileNotFoundError('视频尚未生成')
        size=path.stat().st_size
        first,last=0,size-1
        requested=self.headers.get('Range')
        if requested:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if not m or not any(m.groups()):
                self.respond({'error':'无效的视频范围'},416)
                return
            if not m[1]:
                first=max(0,size-int(m[2]))
            else:
                first=int(m[1]); last=min(last,int(m[2])) if m[2] else last
            if first>last:
                self.send_response(416)
                self.send_header('Content-Range',f'bytes */{size}')
                self.send_header('Content-Length','0')
                self.end_headers()
                return
        self.send_response(206 if requested else 200)
        self.send_header('Content-Type','video/mp4')
        self.send_header('Content-Length',str(last-first+1))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','private, no-store')
        if requested: self.send_header('Content-Range',f'bytes {first}-{last}/{size}')
        self.end_headers()
        if self.command=='HEAD': return
        with path.open('rb') as source:
            source.seek(first)
            remaining=last-first+1
            while remaining:
                chunk=source.read(min(1024*1024,remaining))
                if not chunk: break
                self.wfile.write(chunk)
                remaining-=len(chunk)


if __name__=='__main__':
    host=os.environ.get('HOST','127.0.0.1')
    if host!='127.0.0.1' and len(os.environ.get('APP_TOKEN',''))<32:
        raise SystemExit('Public bind requires APP_TOKEN with at least 32 characters and HTTPS at the proxy.')
    server=ThreadingHTTPServer((host,int(os.environ.get('PORT','8765'))),Handler)
    cert,key=os.environ.get('TLS_CERT'),os.environ.get('TLS_KEY')
    if bool(cert)!=bool(key):
        raise SystemExit('Set both TLS_CERT and TLS_KEY for local HTTPS.')
    if cert:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert,key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
    print(f'Hoop Journal API ready on {host}:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nCoach B service stopped; training records are preserved.',flush=True)
    finally:
        server.server_close()
