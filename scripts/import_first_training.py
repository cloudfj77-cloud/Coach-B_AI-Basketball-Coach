"""Import previously reviewed first training locally; never uploads personal media."""
import argparse
import shutil
import uuid
from server.main import DATA, get, save, launch
from server.media import probe

parser=argparse.ArgumentParser()
parser.add_argument('video')
parser.add_argument('--date',default='日期待确认')
args=parser.parse_args()
ident='4cd58570-87de-4333-b513-5e8f23e99421'
try:
    get(ident)
except FileNotFoundError:
    folder=DATA/ident
    folder.mkdir(exist_ok=True)
    shutil.copyfile(args.video,folder/'source.mov')
    duration=probe(folder/'source.mov')
    releases=[65.3,69.3,92.7,107.7,132.6,141.3,161.5,179.2,201,219.1,237.6,250,263,269.3,282.6,289.2,307.5,323.9,340.7]
    makes={2,6,14,16,17,19}
    shots=[dict(id=str(uuid.uuid4()),start=t-1.8,release=t,end=min(t+2.8,duration),outcome='made' if i in makes else 'missed',reviewed=True,note='从此前人工逐球复盘导入；可在原片中再次核对。') for i,t in enumerate(releases,1)]
    doc=dict(id=ident,title='第一次训练 · 蓝色 2 号',date=args.date,player='蓝色短袖 2 号，白色短裤；不是深色无袖 12 号',duration=duration,shots=shots,revision=1,turns=2,busy=False,status='已导入人工复盘',error='')
    save(doc)
    launch(ident,'prepare')
    print('Imported 19 reviewed attempts / 6 made. Preparing upright video; date awaits confirmation.')
else:
    print('First training already exists; nothing changed.')
