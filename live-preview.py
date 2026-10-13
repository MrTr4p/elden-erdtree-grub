#!/usr/bin/env python3
"""Local interactive viewer for the actual preview VM; never attaches host disks."""
import argparse
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

BASE = Path(__file__).resolve().parent
from preview_tools import tools, preview_env, firmware_args
TOOLS = tools()
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--no-open', action='store_true')
args = parser.parse_args()
TOKEN = secrets.token_urlsafe(24)
runtime = tempfile.TemporaryDirectory(prefix='erdtree-vm-')
work = Path(runtime.name)
qmp = work/'qmp.sock'
env = preview_env(TOOLS)
iso = BASE/'previews/1920x1080/preview.iso'
if not iso.exists(): raise SystemExit('Run python3 preview.py first.')
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
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Erdtree — live boot menu preview</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#050605;color:#ceba8f;font:14px Georgia,serif;height:100vh;display:flex;flex-direction:column}
main{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}img{width:100%;height:100%;object-fit:contain}
footer{display:flex;gap:20px;align-items:center;justify-content:center;flex-wrap:wrap;padding:12px;background:#0c0d0b;border-top:1px solid #51452b}
button{background:transparent;border:1px solid #6a5731;color:#e4cea3;padding:9px 18px;font:inherit;cursor:pointer}
button:hover,button:focus-visible{background:#322918}#status{font-size:12px;color:#97856b}
</style><main><img id="screen" alt="Live Elden Ring boot menu preview"></main>
<footer><span>PREVIEW</span><button data-key="up">↑</button><button data-key="down">↓</button>
<button data-key="ret">Enter / confirm</button><button data-key="esc">Back</button>
<span id="status">Arrow keys select · Enter confirms · No operating system is booted</span></footer>
<script>
const token=new URLSearchParams(location.search).get('token'),screen=document.querySelector('#screen');
let previous, stopped=false, requests=Promise.resolve();
async function update(){
 try{
  const response=await fetch('/frame?token='+token,{cache:'no-store'});
  if(!response.ok)throw Error('Preview stopped');
  const next=URL.createObjectURL(await response.blob());
  await new Promise((resolve,reject)=>{screen.onload=resolve;screen.onerror=reject;screen.src=next;});
  if(previous)URL.revokeObjectURL(previous);previous=next;
 }catch(e){document.querySelector('#status').textContent='Preview stopped. Relaunch live-preview.py to try again.';stopped=true;}
 if(!stopped)setTimeout(update,16);
}
function key(k){
 requests=requests.then(()=>fetch('/key?token='+token,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})}));
}
document.querySelectorAll('[data-key]').forEach(button=>button.onclick=()=>key(button.dataset.key));
window.addEventListener('keydown',event=>{
 const k={ArrowUp:'up',ArrowDown:'down',Enter:'ret',Escape:'esc',Home:'home',End:'end'}[event.key];
 if(k){event.preventDefault();key(k);}
});
update();
</script></html>'''
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
            if path=='/': return self.reply(page.encode(),'text/html; charset=utf-8')
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
    (BASE/'live-preview-url.txt').write_text(url+'\n')
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
