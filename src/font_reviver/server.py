"""Loopback-only HTTP adapter; stable JSON API for any local UI or agent."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from pathlib import Path
import json
import mimetypes
import secrets
import threading
import webbrowser
from .engine import scan_folder, convert_folder


class App:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.state = {"running": False, "phase": "idle"}
        self.output = None
        self.allowed = set()

    def start(self, command, options):
        with self.lock:
            if self.state["running"]:
                raise ValueError("A job is already running")
            self.state = {"running": True, "phase": command, "progress": {}}
        def work():
            try:
                source = options["source"]
                output = options.get("output") or None
                if not isinstance(source, str) or (output is not None and not isinstance(output, str)):
                    raise ValueError("source/output must be folder path strings")
                if command == "scan":
                    result = scan_folder(source, output, archives=options.get("archives", True))
                else:
                    def progress(event):
                        with self.lock:
                            self.state["progress"] = event
                    result = convert_folder(source, output, archives=options.get("archives", True),
                                            jobs=int(options.get("jobs", 4)), progress=progress)
                    with self.lock:
                        self.output = Path(result["output_root"])
                        self.allowed = {"Gallery.html", "report.json", "results.csv"} | {
                            item["output"] for row in result["records"] for item in row["fonts"] if "output" in item}
                with self.lock:
                    self.state = {"running": False, "phase": "complete", "operation": command,
                                  "summary": result["summary"], "output_root": result["output_root"],
                                  "gallery": f"/results/{self.token}/Gallery.html" if command == "convert" else None}
            except Exception as error:
                with self.lock:
                    self.state = {"running": False, "phase": "error", "error": str(error)}
        threading.Thread(target=work, daemon=True).start()


def make_server(port=0):
    app = App()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log paths or the per-session access token.

        def send(self, status, data, content_type="application/json"):
            body = json.dumps(data).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def host_ok(self):
            port = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (not origin or origin in {"http://"+h for h in hosts})

        def authenticated(self):
            return secrets.compare_digest(self.headers.get("X-Font-Reviver-Token", ""), app.token)

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, {"error": "Local host/origin required"})
            path = unquote(urlsplit(self.path).path)
            if path == "/":
                return self.send(200, Path(__file__).with_name("app.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/status" and self.authenticated():
                with app.lock:
                    return self.send(200, dict(app.state))
            if path == "/api/doctor" and self.authenticated():
                from .cli import doctor
                return self.send(200, doctor())
            prefix = f"/results/{app.token}/"
            if path.startswith(prefix):
                relative = path[len(prefix):]
                with app.lock:
                    output, allowed = app.output, set(app.allowed)
                if output and relative in allowed:
                    file = (output/relative).resolve()
                    if output in file.parents and file.is_file():
                        return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                return self.send(404, {"error": "Result not found"})
            return self.send(403, {"error": "Session token required"})

        def do_POST(self):
            if not self.host_ok() or not self.authenticated():
                return self.send(403, {"error": "Local session token required"})
            path = urlsplit(self.path).path
            if path not in {"/api/scan", "/api/convert"}:
                return self.send(404, {"error": "Unknown endpoint"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384:
                    raise ValueError("JSON body must be 1–16384 bytes")
                options = json.loads(self.rfile.read(size))
                if not isinstance(options, dict) or "source" not in options:
                    raise ValueError("A source folder is required")
                app.start(path.rsplit("/", 1)[1], options)
                self.send(202, {"accepted": True, "status": "/api/status"})
            except (ValueError, TypeError) as error:
                self.send(400, {"error": str(error)})
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, app


def serve(port=0, open_browser=True):
    server, app = make_server(port)
    address = f"http://127.0.0.1:{server.server_address[1]}/#{app.token}"
    print(json.dumps({"schema_version": 1, "url": address, "token": app.token,
                      "note": "Keep the local session token private. Ctrl+C stops the server."}), flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
