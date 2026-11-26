"""Yerel HTTP uygulaması."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .analysis import validate_form
from .llm import EvaluationError, SYSTEM_PROMPT

MAX_BODY = 64 * 1024
STATIC = Path(__file__).resolve().parent / "static"
ASSETS = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
    "/analysis.mjs": ("analysis.mjs", "text/javascript"),
    "/demo.mjs": ("demo.mjs", "text/javascript"),
    "/config.mjs": ("config.mjs", "text/javascript"),
}


def prompt_module():
    return f"export const systemPrompt = {json.dumps(SYSTEM_PROMPT)};\n".encode()


class WorkshopServer(ThreadingHTTPServer):
    def __init__(self, address, provider):
        self.provider = provider
        super().__init__(address, WorkshopHandler)

    def handle_error(self, request, client_address):
        # İstek verilerinin hata çıktısına taşınmasını önle.
        pass


class WorkshopHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.fail(code, "HTTP isteği işlenemedi.")

    def send_bytes(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, data):
        self.send_bytes(status, "application/json", json.dumps(data, ensure_ascii=False).encode())

    def fail(self, status, message):
        self.send_json(status, {"hata": message})

    def host_allowed(self):
        # DNS rebinding'e karşı: yalnızca sunucunun kendi adresiyle gelen isteklere yanıt ver.
        host, port = self.server.server_address[:2]
        names = {"127.0.0.1", "localhost", "[::1]"}
        if host not in ("", "0.0.0.0", "::"):
            names.add(f"[{host}]" if ":" in host else host)
        allowed = {f"{name}:{port}" for name in names}
        if port == 80:
            allowed |= names
        values = self.headers.get_all("Host", [])
        if len(values) == 1 and values[0].lower() in allowed:
            return True
        self.fail(403, "Bu adres üzerinden erişime izin verilmiyor.")
        return False

    def do_GET(self):
        if not self.host_allowed():
            return
        try:
            path = urlsplit(self.path).path
        except ValueError:
            self.fail(400, "Adres geçersiz.")
            return
        if path == "/api/durum":
            self.send_json(200, self.server.provider.status())
        elif path == "/prompt.mjs":
            self.send_bytes(200, "text/javascript", prompt_module())
        elif path in ASSETS:
            filename, content_type = ASSETS[path]
            self.send_bytes(200, content_type, (STATIC / filename).read_bytes())
        else:
            self.fail(404, "Sayfa bulunamadı.")

    do_HEAD = do_GET

    def do_POST(self):
        if not self.host_allowed():
            return
        if self.path != "/api/degerlendir":
            self.fail(404, "Uç nokta bulunamadı.")
            return
        if self.headers.get_all("X-Atolye-Request") != ["1"]:
            self.fail(403, "Atölye istek başlığı eksik veya geçersiz.")
            return

        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1
                or not re.fullmatch(r"[0-9]+", lengths[0])):
            self.fail(400, "İstek uzunluğu geçersiz.")
            return
        digits = lengths[0].lstrip("0") or "0"
        if len(digits) > len(str(MAX_BODY)) or int(digits) > MAX_BODY:
            self.fail(413, "İstek gövdesi 64 KB sınırını aşıyor.")
            return
        if self.headers.get_content_type() != "application/json":
            self.fail(400, "İstek gövdesi JSON olmalı.")
            return
        try:
            data = json.loads(self.rfile.read(int(digits)).decode("utf-8"))
        except (ValueError, RecursionError, TimeoutError):
            self.fail(400, "İstek gövdesi geçerli UTF-8 JSON olmalı.")
            return
        try:
            form = validate_form(data)
        except ValueError as exc:
            self.fail(400, str(exc))
            return

        try:
            result = self.server.provider.evaluate(form)
        except EvaluationError as exc:
            self.fail(502, str(exc))
            return
        self.send_json(200, result)
