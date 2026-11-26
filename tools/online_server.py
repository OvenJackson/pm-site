"""在线版服务：静态网站 + 共享数据 + SSE 实时推送。

环境变量：
  PORT        监听端口（Render/Railway 自动提供）
  EDIT_TOKEN  可选编辑口令；设置后仅携带 ?edit=口令 的编辑者可保存
  STATE_FILE  可选状态文件路径（默认 data/online_state.json）
"""
import http.server
import json
import os
import queue
import re
import socketserver
import threading

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("PORT") or 8765)
EDIT_TOKEN = os.environ.get("EDIT_TOKEN") or ""
STATE_FILE = os.environ.get("STATE_FILE") or os.path.join(BASE, "data", "online_state.json")

_lock = threading.Lock()
_clients = []
_version = 0
_state = {"app": {}, "ov": {}, "ts": 0}


def read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict):
                return d
    except (OSError, ValueError):
        pass
    # 首次启动时尝试从本地修改文件初始化
    try:
        p = os.path.join(BASE, "data", "local_overrides.js")
        with open(p, "r", encoding="utf-8") as f:
            s = f.read()
        m = re.search(r"window\.PM_LOCAL_FILE\s*=\s*(\{.*\});?\s*$", s, re.S)
        if m:
            d = json.loads(m.group(1))
            if isinstance(d, dict):
                return d
    except (OSError, ValueError):
        pass
    return {"app": {}, "ov": {}, "ts": 0}


def write_state(d):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, STATE_FILE)


def broadcast():
    for q in list(_clients):
        try:
            q.put_nowait(str(_version))
        except Exception:
            pass


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def send_bytes(self, body, ctype, code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            with _lock:
                body = json.dumps(_state, ensure_ascii=False).encode("utf-8")
            self.send_bytes(body, "application/json; charset=utf-8")
            return
        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = queue.Queue()
            with _lock:
                _clients.append(q)
            try:
                self.wfile.write(("retry: 3000\n\n").encode("utf-8"))
                self.wfile.flush()
                while True:
                    try:
                        v = q.get(timeout=20)
                        self.wfile.write(("event: state\ndata: %s\n\n" % v).encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with _lock:
                    if q in _clients:
                        _clients.remove(q)
            return
        if path in ("/", "/index.html"):
            self.serve_index()
            return
        super().do_GET()

    def serve_index(self):
        try:
            with open(os.path.join(BASE, "index.html"), "r", encoding="utf-8") as f:
                html = f.read()
        except OSError:
            self.send_error(404)
            return
        with _lock:
            payload = dict(_state)
        js = json.dumps(payload, ensure_ascii=False).replace("</script", "<\\/script")
        inject = ('<script>window.PM_ONLINE_STATE = ' + js +
                  ';window.PM_ONLINE_REQUIRED = ' + ('true' if EDIT_TOKEN else 'false') + ';</script>\n')
        marker = '<script src="data/local_overrides.js"></script>'
        if marker in html:
            html = html.replace(marker, inject + marker, 1)
        else:
            html = html.replace("</head>", inject + "</head>", 1)
        self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/api/state":
            self.send_error(404)
            return
        global _state, _version
        if EDIT_TOKEN:
            token = self.headers.get("X-Edit-Token") or ""
            if not token:
                qs = self.path.split("?", 1)[1] if "?" in self.path else ""
                m = re.search(r"(?:^|&)token=([^&]+)", qs)
                token = m.group(1) if m else ""
            if token != EDIT_TOKEN:
                self.send_bytes(b'{"ok":false,"error":"unauthorized"}', "application/json", 403)
                return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            d = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(d, dict) or "app" not in d or "ov" not in d:
                raise ValueError("bad payload")
            d["ts"] = int(d.get("ts") or 0) or int(__import__("time").time() * 1000)
            write_state(d)
            with _lock:
                _state = d
                _version += 1
            broadcast()
            self.send_bytes(b'{"ok":true}', "application/json; charset=utf-8")
        except Exception as e:  # noqa: BLE001
            self.send_bytes(("error: %s" % e).encode("utf-8"), "text/plain; charset=utf-8", 400)

    def log_message(self, fmt, *args):
        pass


def main():
    global _state
    _state = read_state()
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.daemon_threads = True
        print("online server: http://0.0.0.0:%d  (state=%s, token=%s)" % (PORT, STATE_FILE, "on" if EDIT_TOKEN else "off"))
        httpd.serve_forever()


if __name__ == "__main__":
    main()