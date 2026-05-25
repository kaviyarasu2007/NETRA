from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
from pathlib import Path
import sqlite3
import os
import json
import mimetypes
import time
import uuid

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "approvals.db"

UPLOAD_DIR.mkdir(exist_ok=True)
SITE_DIR.mkdir(exist_ok=True)

INDEX_HTML = SITE_DIR / "index.html"
WAIT_SECONDS = 30
POLL_INTERVAL = 0.5


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL,
            client_ip TEXT,
            created_at REAL NOT NULL,
            decided_at REAL,
            action TEXT,
            filename TEXT,
            file_size INTEGER,
            meta_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def create_request_record(method, path, client_ip, filename=None, file_size=None, meta=None):
    req_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute("""
        INSERT INTO requests (
            id, method, path, status, client_ip, created_at,
            filename, file_size, meta_json
        ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
    """, (
        req_id,
        method,
        path,
        client_ip,
        time.time(),
        filename,
        file_size,
        json.dumps(meta or {})
    ))
    conn.commit()
    conn.close()
    return req_id


def wait_for_decision(req_id, timeout=WAIT_SECONDS):
    deadline = time.time() + timeout

    while time.time() < deadline:
        conn = get_db()
        row = conn.execute(
            "SELECT status, action FROM requests WHERE id=?",
            (req_id,)
        ).fetchone()
        conn.close()

        if row and row["status"] == "decided":
            return row["action"]

        time.sleep(POLL_INTERVAL)

    conn = get_db()
    conn.execute("""
        UPDATE requests
        SET status='decided', action='timeout', decided_at=?
        WHERE id=? AND status='pending'
    """, (time.time(), req_id))
    conn.commit()
    conn.close()
    return "timeout"


def html_response(handler, body, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(body.encode("utf-8"))


def json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(json.dumps(data, indent=2).encode("utf-8"))


def file_list_html():
    items = []
    for f in sorted(UPLOAD_DIR.iterdir()):
        if f.is_file():
            size = f.stat().st_size
            items.append(f'<li><a href="/download/{f.name}">{f.name}</a> ({size} bytes)</li>')

    if not items:
        return "<p>No uploaded files yet.</p>"

    return "<ul>" + "".join(items) + "</ul>"


def parse_multipart_file(handler):
    content_type = handler.headers.get("Content-Type", "")
    if "boundary=" not in content_type:
        return None, "Missing boundary"

    boundary = content_type.split("boundary=")[-1].strip().encode()
    content_length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(content_length)

    parts = body.split(b"--" + boundary)

    for part in parts:
        if b'name="file"' in part and b"filename=" in part:
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers_block = part[:header_end].decode(errors="ignore")
            data = part[header_end + 4:]

            if data.endswith(b"\r\n"):
                data = data[:-2]
            if data.endswith(b"--"):
                data = data[:-2]

            filename = None
            for line in headers_block.split("\r\n"):
                if "filename=" in line:
                    filename = line.split("filename=")[-1].strip().strip('"')
                    break

            if not filename:
                return None, "No filename found"

            safe_name = os.path.basename(filename)
            return {
                "filename": safe_name,
                "data": data
            }, None

    return None, "No file field found"


class FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            req_id = create_request_record("GET", path, self.client_address[0])
            decision = wait_for_decision(req_id)

            if decision != "allow":
                html_response(self, f"<h1>Request blocked: {decision}</h1>", 403)
                return

            if INDEX_HTML.exists():
                content = INDEX_HTML.read_text(encoding="utf-8")
                content = content.replace("{{FILE_LIST}}", file_list_html())
                html_response(self, content)
            else:
                html_response(self, "<h1>index.html not found</h1>", 404)
            return

        elif path == "/files":
            req_id = create_request_record("GET", path, self.client_address[0])
            decision = wait_for_decision(req_id)

            if decision != "allow":
                json_response(self, {"error": f"Request blocked: {decision}"}, 403)
                return

            files = []
            for f in sorted(UPLOAD_DIR.iterdir()):
                if f.is_file():
                    files.append({
                        "name": f.name,
                        "size": f.stat().st_size
                    })

            json_response(self, {"files": files})
            return

        elif path.startswith("/download/"):
            filename = unquote(path.replace("/download/", "", 1))
            file_path = UPLOAD_DIR / filename

            req_id = create_request_record(
                "GET",
                path,
                self.client_address[0],
                filename=filename,
                file_size=file_path.stat().st_size if file_path.exists() and file_path.is_file() else None
            )
            decision = wait_for_decision(req_id)

            if decision != "allow":
                html_response(self, f"<h1>Request blocked: {decision}</h1>", 403)
                return

            if not file_path.exists() or not file_path.is_file():
                html_response(self, "<h1>File not found</h1>", 404)
                return

            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(str(file_path))
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.end_headers()

            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        else:
            html_response(self, "<h1>404 Not Found</h1>", 404)

    def do_POST(self):
        if self.path != "/upload":
            html_response(self, "<h1>404 Not Found</h1>", 404)
            return

        result, err = parse_multipart_file(self)
        if err:
            html_response(self, f"<h1>Upload error: {err}</h1>", 400)
            return

        req_id = create_request_record(
            "POST",
            self.path,
            self.client_address[0],
            filename=result["filename"],
            file_size=len(result["data"])
        )
        decision = wait_for_decision(req_id)

        if decision != "allow":
            html_response(self, f"<h1>Upload blocked: {decision}</h1>", 403)
            return

        save_path = UPLOAD_DIR / result["filename"]
        with open(save_path, "wb") as f:
            f.write(result["data"])

        html_response(
            self,
            f"""<html>
<body>
<h2>Upload successful</h2>
<p>Saved: {result["filename"]}</p>
<a href="/">Go back</a>
</body>
</html>"""
        )


if __name__ == "__main__":
    init_db()
    print("Serving file site on http://0.0.0.0:8000")
    server = HTTPServer(("0.0.0.0", 8000), FileHandler)
    server.serve_forever()
