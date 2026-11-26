"""本地网站服务：提供页面访问，并把页面修改持久化到 data/local_overrides.json。"""
import http.server
import json
import os
import socketserver
import threading
import webbrowser

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE = os.path.join(BASE, "data", "local_overrides.json")
PORT = 8765


def read_save():
    try:
        with open(SAVE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_save(data):
    os.makedirs(os.path.dirname(SAVE), exist_ok=True)
    tmp = SAVE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, SAVE)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def send_body(self, body, ctype, code=200):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if self.path.startswith("/api/"):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/local-overrides.js":
            data = read_save()
            body = "window.PM_LOCAL_SAVE = " + json.dumps(data, ensure_ascii=False) + ";"
            self.send_body(body, "application/javascript; charset=utf-8")
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/save-overrides":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("bad payload")
            write_save(data)
            self.send_body("ok", "text/plain; charset=utf-8", 200)
        except Exception as e:  # noqa: BLE001
            self.send_body("error: %s" % e, "text/plain; charset=utf-8", 400)

    def end_headers(self):
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        threading.Timer(0.6, lambda: webbrowser.open("http://127.0.0.1:%d/index.html" % PORT)).start()
        print("项目管理网站已启动：http://127.0.0.1:%d/index.html" % PORT)
        print("关闭此窗口即停止服务。修改会保存到 data/local_overrides.json")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
