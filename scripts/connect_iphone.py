"""Provision the development App over USB without printing or embedding secrets."""
import argparse
import base64
import json
import os
from pathlib import Path
import ssl
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--device', required=True)
parser.add_argument('--console', action='store_true', help='Show App diagnostics until it exits')
args = parser.parse_args()
local = root/'data'/'local'
config = json.loads((local/'settings.json').read_text())
der = ssl.PEM_cert_to_DER_cert((local/'server.pem').read_text())
env = dict(os.environ,
           DEVICECTL_CHILD_HOOP_LOCAL_SERVER='https://'+config['name']+':8766',
           DEVICECTL_CHILD_HOOP_LOCAL_TOKEN=(root/'data'/'.token').read_text().strip(),
           DEVICECTL_CHILD_HOOP_LOCAL_CERT=base64.b64encode(der).decode())
subprocess.run(['xcrun', 'devicectl', 'device', 'process', 'launch', '--terminate-existing', *(['--console'] if args.console else []),
                '--device', args.device, 'com.cloud77luke.hoopjournal'], env=env, check=True)
