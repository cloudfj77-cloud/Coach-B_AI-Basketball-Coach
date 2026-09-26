"""Run the personal, free Mac service with TLS; secrets remain in ignored data/."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'data' / 'local'


def prepare(name, bind, python, ffmpeg):
    LOCAL.mkdir(parents=True, exist_ok=True)
    LOCAL.chmod(0o700)
    settings = dict(name=name, bind=bind, python=python, ffmpeg=ffmpeg)
    settings_file = LOCAL / 'settings.json'
    old = json.loads(settings_file.read_text()) if settings_file.exists() else {}
    cert, key = LOCAL / 'server.pem', LOCAL / 'server.key'
    # Hostnames are used in an OpenSSL config, so only DNS names or IP literals fit.
    try:
        address = ipaddress.ip_address(name)
        san = 'IP:' + str(address)
    except ValueError:
        import re
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', name):
            raise ValueError('Invalid Mac hostname')
        san = 'DNS:' + name
    if not cert.exists() or not key.exists() or old.get('name') != name:
        conf = LOCAL / 'certificate.cnf'
        conf.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n'
                        '[dn]\nCN=Coach B Personal Mac\n[ext]\nsubjectAltName=' + san + '\n'
                        'basicConstraints=critical,CA:TRUE,pathlen:0\n'
                        'keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\n'
                        'extendedKeyUsage=serverAuth\n')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-days', '365', '-keyout', str(key), '-out', str(cert),
                        '-config', str(conf)], check=True, capture_output=True)
        key.chmod(0o600)
    token = ROOT / 'data' / '.token'
    if not token.exists():
        token.write_text(secrets.token_urlsafe(32))
    token.chmod(0o600)
    settings_file.write_text(json.dumps(settings, indent=2))
    settings_file.chmod(0o600)
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='Mac .local hostname or current private IP')
    parser.add_argument('--bind', help='Local interface IP; default 0.0.0.0')
    parser.add_argument('--python', help='Python with Pillow installed')
    parser.add_argument('--ffmpeg', help='FFmpeg binary with libx264 and zscale')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    old = json.loads((LOCAL/'settings.json').read_text()) if (LOCAL/'settings.json').exists() else {}
    name = args.name or old.get('name') or subprocess.check_output(['scutil', '--get', 'LocalHostName'], text=True).strip()+'.local'
    config = prepare(name, args.bind or old.get('bind', '0.0.0.0'),
                     args.python or old.get('python', sys.executable),
                     args.ffmpeg or old.get('ffmpeg') or shutil.which('ffmpeg') or '')
    if not config['ffmpeg'] or not Path(config['ffmpeg']).is_file():
        raise SystemExit('First setup needs --ffmpeg /path/to/ffmpeg')
    print('Coach B local service: https://' + name + ':8766', flush=True)
    print('Keep this window open. AI API calls are disabled in free Mac mode.', flush=True)
    if args.prepare_only:
        return
    env = dict(os.environ, DATA_DIR=str(ROOT/'data'), HOST=config['bind'], PORT='8766',
               APP_TOKEN=(ROOT/'data'/'.token').read_text().strip(),
               TLS_CERT=str(LOCAL/'server.pem'), TLS_KEY=str(LOCAL/'server.key'),
               LOCAL_ACCESS_LOG='1', FFMPEG_PATH=config['ffmpeg'])
    env.setdefault('FONT_PATH', '/System/Library/Fonts/Hiragino Sans GB.ttc')
    env.pop('OPENAI_API_KEY', None)
    # No permanent system setting changes: sleep prevention ends with this process.
    os.chdir(ROOT)
    os.execvpe('caffeinate', ['caffeinate', '-i', config['python'], '-m', 'server.main'], env)


if __name__ == '__main__':
    main()
