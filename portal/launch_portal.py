#!/usr/bin/env python3
"""
Stack n Stock — Study Portal Local Server & Data Receiver
Launches a lightweight HTTP server serving the portal directory, provides an
endpoint (/api/save_csv) to save exported trial data directly with timestamps
into data/raw/, and automatically launches the web browser.
"""

import sys
import os
import socket
import argparse
import json
import threading
import webbrowser
import traceback
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from study_store import StudyStore, StoreError, analyze

PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
# Bundled web assets extract to PyInstaller's temporary directory; persistent
# study data must instead remain next to the portable executable.
PROJECT_ROOT = (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
                else os.path.abspath(os.path.join(PORTAL_DIR, "..")))
DATA_RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
STORE = StudyStore(os.environ.get('SNS_STUDY_DB', os.path.join(PROJECT_ROOT, 'data', 'study_sessions.sqlite3')))


def find_available_port(start_port=8000, max_attempts=50):
    """Find an open TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port + max_attempts}")


class PortalRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Stack n Stock Study Portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PORTAL_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.study_api('GET')
        # Route root requests directly to the portal HTML
        if self.path in ("/", "", "/index.html"):
            self.path = "/sns_study_portal.html"
        return super().do_GET()

    def do_OPTIONS(self):
        # Support CORS pre-flight requests
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        # Endpoint to receive and persist exported CSV data directly into data/raw/
        if self.path == "/api/save_csv":
            self.handle_save_csv()
        elif self.path.startswith('/api/'):
            self.study_api('POST')
        else:
            self.send_error(404, "Endpoint not found")

    def study_api(self, method):
        try:
            origin = self.headers.get('Origin')
            if method == 'POST' and origin and origin != 'http://' + self.headers.get('Host', ''):
                raise StoreError('Study changes must come from this local workspace', 403)
            parts = urlparse(self.path).path.strip('/').split('/')
            payload = None
            if method == 'POST':
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 32 * 1024 * 1024:
                    raise StoreError('Invalid request size', 413)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise StoreError('Request must be a JSON object')
            if parts == ['api','presets']:
                result = STORE.presets(payload)
            elif parts == ['api','sessions'] and method == 'GET':
                result = STORE.list()
            elif len(parts) >= 3 and parts[:2] == ['api','sessions']:
                sid = parts[2]
                if len(parts) == 3 and method == 'GET':
                    result = STORE.get(sid)
                elif parts[3:] == ['claim'] and method == 'POST':
                    result = STORE.claim(sid, payload.get('writer'))
                elif parts[3:] == ['save'] and method == 'POST':
                    result = STORE.save(sid, payload)
                elif parts[3:] == ['analysis'] and method == 'GET':
                    result = analyze(STORE.get(sid)['snapshot'])
                else:
                    raise StoreError('Endpoint not found', 404)
            else:
                raise StoreError('Endpoint not found', 404)
            self.json_response(200, result)
        except StoreError as exc:
            self.json_response(exc.status, {'error': str(exc)})
        except (ValueError, TypeError, KeyError) as exc:
            self.json_response(400, {'error': 'Invalid request: ' + str(exc)})
        except Exception as exc:
            self.log_error('Study storage error: %s', exc)
            self.json_response(500, {'error': 'Local storage is unavailable. Pending data must be retained and retried.'})

    def json_response(self, status, payload):
        data = json.dumps(payload, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_save_csv(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8", errors="replace")

        try:
            payload = json.loads(post_data)
            csv_content = payload.get("csv", payload.get("content", ""))
            original_filename = payload.get("filename", "")
        except json.JSONDecodeError:
            # Fallback for plain text / direct CSV body
            csv_content = post_data
            original_filename = self.headers.get("X-Filename", "")

        if not csv_content.strip():
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_resp = {"status": "error", "message": "CSV content is empty."}
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))
            return

        # Ensure destination directory exists
        os.makedirs(DATA_RAW_DIR, exist_ok=True)

        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")

        if original_filename:
            base, ext = os.path.splitext(original_filename)
            ext = ext if ext else ".csv"
            clean_base = os.path.basename(base)
            target_filename = f"{clean_base}_{timestamp_str}{ext}"
        else:
            target_filename = f"SNS_Study_export_{timestamp_str}.csv"

        target_path = os.path.join(DATA_RAW_DIR, target_filename)

        try:
            with open(target_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_content)

            file_size = os.path.getsize(target_path)
            print(f"\n[API /api/save_csv] Saved CSV: {target_filename} ({file_size} bytes)")
            print(f"                 Full Path: {target_path}")

            response_data = {
                "status": "success",
                "message": "CSV saved successfully to data/raw/",
                "filename": target_filename,
                "filepath": target_path,
                "bytes_written": file_size,
                "timestamp": now.isoformat()
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))

        except Exception as e:
            print(f"\n[API /api/save_csv] Error writing file: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_resp = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))

    def log_message(self, format, *args):
        # Override to provide concise server logging
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")


class LocalPortalServer(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def bind_server(port):
    # Hold the chosen socket, avoiding the race between probing and binding.
    for candidate in range(port, min(port + 50, 65536)):
        try:
            return LocalPortalServer(('127.0.0.1', candidate), PortalRequestHandler)
        except OSError as exc:
            if exc.errno not in (13, 48, 98, 10013, 10048):
                raise
    raise RuntimeError('No available local port. Close an unused portal window and try again.')


def run_server(port=8765, open_browser_flag=True):
    httpd = bind_server(port)
    actual_port = httpd.server_port
    url = f"http://127.0.0.1:{actual_port}/sns_study_portal.html"

    os.makedirs(DATA_RAW_DIR, exist_ok=True)

    if getattr(sys, 'frozen', False):
        with open(os.path.join(PROJECT_ROOT, 'Open Portal.html'), 'w', encoding='utf-8') as shortcut:
            shortcut.write(f'<!doctype html><meta http-equiv="refresh" content="0;url={url}"><a href="{url}">Open study portal</a>')

    print("=" * 70)
    print("   STACK N STOCK — PICK & PACK STUDY PORTAL LOCAL SERVER")
    print("=" * 70)
    print(f" * Portal URL         : {url}")
    print(f" * Serving Directory  : {PORTAL_DIR}")
    print(f" * Raw Data Directory : {DATA_RAW_DIR}")
    print(f" * Save Endpoint      : http://localhost:{actual_port}/api/save_csv")
    print("=" * 70)
    print(" Press Ctrl+C in this console to stop the server at any time.\n")

    if open_browser_flag:
        def launch():
            print(f" Launching default browser to: {url} ...")
            webbrowser.open(url)
        threading.Timer(0.8, launch).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n [INFO] Received shutdown signal. Stopping local server...")
    finally:
        httpd.server_close()
        print(" [INFO] Server stopped. Goodbye!\n")


def main():
    parser = argparse.ArgumentParser(description="Stack n Stock Study Portal Local Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    run_server(port=args.port, open_browser_flag=not args.no_browser)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        details = traceback.format_exc()
        print(details, file=sys.stderr)
        if getattr(sys, 'frozen', False):
            log_path = os.path.join(PROJECT_ROOT, 'portal-startup-error.txt')
            try:
                with open(log_path, 'w', encoding='utf-8') as log:
                    log.write(details)
            except OSError:
                pass
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, 'The portal could not start.\n\n' + details[-1200:] + '\n\nLog: ' + log_path, 'Stack n Stock Portal', 16)
        sys.exit(1)
