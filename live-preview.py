#!/usr/bin/env python3
"""Local interactive viewer for the actual preview VM; never attaches host disks."""
import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
from PIL import Image
from variants import VARIANTS, preview_tag, url_path

BASE = Path(__file__).resolve().parent
from preview_tools import tools, preview_env, firmware_args
TOOLS = tools()
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--variant', choices=VARIANTS, default='grace')
parser.add_argument('--no-open', action='store_true')
parser.add_argument('--static', action='store_true', help='Use the static preview ISO')
parser.add_argument('--no-ambient', action='store_true', help='Use the selection-only preview ISO')
args = parser.parse_args()
TOKEN = secrets.token_urlsafe(24)
saved_url = url_path(args.variant)
if saved_url.exists():
    saved_token = urllib.parse.parse_qs(urllib.parse.urlsplit(saved_url.read_text().strip()).query).get('token', [''])[0]
    if len(saved_token) == 32 and all(c.isalnum() or c in '-_' for c in saved_token):
        TOKEN = saved_token
runtime = tempfile.TemporaryDirectory(prefix='erdtree-vm-')
work = Path(runtime.name)
qmp = work/'qmp.sock'
env = preview_env(TOOLS)
tag = preview_tag('1920x1080', args.variant, '-static' if args.static else '-no-ambient' if args.no_ambient else '')
iso = BASE/'previews'/tag/'preview.iso'
if not iso.exists(): raise SystemExit('Run python3 preview.py with the same mode flags first.')
command = [TOOLS['qemu'], '-L', TOOLS['qemu_data'],
    '-machine','q35','-accel',TOOLS['accel'],'-cpu',TOOLS['cpu'],'-m','512','-vga','std',
    *firmware_args(TOOLS, work),'-display','none',
    '-nic','none','-no-reboot','-boot','order=d',
    '-drive',f'file={iso},media=cdrom,readonly=on',
    '-serial',f'file:{work/"serial.log"}','-qmp',f'unix:{qmp},server=on,wait=off']
vm = subprocess.Popen(command,env=env,stdout=subprocess.DEVNULL,stderr=(work/'qemu.log').open('w'))
server = None
sock = None
try:
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(15)
    for _ in range(150):
        if vm.poll() is not None:
            raise RuntimeError((work/'qemu.log').read_text())
        try:
            sock.connect(str(qmp))
            break
        except (FileNotFoundError, ConnectionRefusedError):
            time.sleep(.1)
    else:
        raise RuntimeError('QEMU monitor did not become ready.')
    stream = sock.makefile('rwb',buffering=0)
    stream.readline()
    lock = threading.Lock()
    def rpc(name, arguments=None):
        req = {'execute':name}
        if arguments: req['arguments']=arguments
        stream.write(json.dumps(req).encode()+b'\n')
        while True:
            msg=json.loads(stream.readline())
            if 'error' in msg: raise RuntimeError(msg)
            if 'return' in msg: return msg['return']
    rpc('qmp_capabilities')
    def viewer_page():
        palette = VARIANTS[args.variant]
        page = (BASE/'viewer.html').read_text()
        page = page.replace('Site of Grace — live boot menu', html.escape(palette['title']) + ' — live boot menu')
        page = page.replace('SITE OF GRACE / BOOT MENU', html.escape(palette['title'].upper()) + ' / BOOT MENU')
        page = page.replace('a gently swaying Site of Grace flame and circling golden wisps', html.escape(palette['description']))
        page = page.replace('AWAITING GRACE…', 'ENTERING ' + html.escape(palette['title'].upper()) + '…')
        style = f'''<style>body,main:fullscreen{{background:{palette['background']};color:{palette['text']}}}
header,footer{{background:{palette['panel']};border-color:{palette['accent']}44}}
.brand,button{{color:{palette['selected']}}}button{{background:{palette['panel']};border-color:{palette['accent']}66}}
button:hover{{background:{palette['accent']}22;border-color:{palette['accent']}}}
button:focus-visible{{outline-color:{palette['accent']}}}.dot{{background:{palette['accent']};box-shadow:0 0 9px {palette['accent']}66}}
.live,#status,.loading{{color:{palette['text']}}}.meta{{color:{palette['hint']}}}</style>'''
        return page.replace('</head>', style + '</head>').encode()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def authorized(self):
            return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('token')==[TOKEN]
        def reply(self, data, content_type, status=200):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            try: self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError): pass
        def do_GET(self):
            if not self.authorized(): return self.reply(b'Forbidden','text/plain',403)
            path=urllib.parse.urlsplit(self.path).path
            if path=='/': return self.reply(viewer_page(),'text/html; charset=utf-8')
            if path=='/frame':
                with lock:
                    rpc('screendump',{'filename':str(work/'frame.ppm')})
                    with Image.open(work/'frame.ppm') as image:
                        output=io.BytesIO()
                        image.save(output,format='JPEG',quality=93)
                return self.reply(output.getvalue(),'image/jpeg')
            return self.reply(b'Not found','text/plain',404)
        def do_POST(self):
            if not self.authorized(): return self.reply(b'Forbidden','text/plain',403)
            if urllib.parse.urlsplit(self.path).path!='/key':
                return self.reply(b'Not found','text/plain',404)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<128: raise ValueError()
                key=json.loads(self.rfile.read(length))['key']
                if key not in ['up','down','ret','esc','home','end']: raise ValueError()
            except (ValueError,KeyError):
                return self.reply(b'Invalid key','text/plain',400)
            with lock:
                rpc('send-key',{'keys':[{'type':'qcode','data':key}],'hold-time':40})
            self.reply(b'{"ok":true}','application/json')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}/?token={TOKEN}'
    saved_url.touch(mode=0o600, exist_ok=True)
    saved_url.chmod(0o600)
    saved_url.write_text(url+'\n')
    print(url,flush=True)
    if not args.no_open: subprocess.Popen(['xdg-open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def stop(*_): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    server.serve_forever(poll_interval=.2)
except KeyboardInterrupt:
    pass
finally:
    if server: server.server_close()
    if sock: sock.close()
    if vm.poll() is None:
        vm.terminate()
        vm.wait(timeout=10)
    runtime.cleanup()
