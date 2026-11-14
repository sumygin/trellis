import http.server
import socketserver
import json
import os
import urllib.request
import urllib.parse
import re
import ipaddress
import socket
from html.parser import HTMLParser

PORT = 8000
DATA_FILE = "data.json"
UPLOADS_DIR = "uploads"

os.makedirs(UPLOADS_DIR, exist_ok=True)

DEFAULT_DATA = {
    "activeBoardId": "board-1",
    "boards": [
        {
            "id": "board-1",
            "name": "Personal Board",
            "background": "",
            "lists": [
                {"id": "list-due-today", "name": "DUE TODAY", "cards": []},
                {"id": "list-cs", "name": "CS", "cards": []},
                {"id": "list-personal", "name": "Personal", "cards": []},
                {"id": "list-done", "name": "Done", "cards": []}
            ]
        }
    ]
}

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_DATA, f, indent=2)


class OGImageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.image_url = None
        self.first_img = None

    def handle_starttag(self, tag, attrs):
        attr_dict = {k.lower(): v for k, v in attrs if k and v}
        if tag.lower() == "meta":
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "")
            if content and (prop in ("og:image", "twitter:image") or name in ("og:image", "twitter:image")):
                if not self.image_url:
                    self.image_url = urllib.parse.urljoin(self.base_url, content)
        elif tag.lower() == "img" and not self.first_img:
            src = attr_dict.get("src", "")
            if src and not src.startswith("data:"):
                self.first_img = urllib.parse.urljoin(self.base_url, src)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def extract_link_image(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname:
        return None

    try:
        addresses = socket.getaddrinfo(parsed_url.hostname, None)
        if any(ipaddress.ip_address(address[4][0]).is_private or
               ipaddress.ip_address(address[4][0]).is_loopback or
               ipaddress.ip_address(address[4][0]).is_link_local or
               ipaddress.ip_address(address[4][0]).is_reserved
               for address in addresses):
            return None
    except (socket.gaierror, ValueError):
        return None

    # Direct image URL check
    parsed_path = parsed_url.path.lower()
    if any(parsed_path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif")):
        return url

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        opener = urllib.request.build_opener(NoRedirectHandler)
        with opener.open(req, timeout=4) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if content_type.startswith("image/"):
                return url
            if "text/html" in content_type:
                raw_html = resp.read(250_000).decode("utf-8", errors="ignore")
                parser = OGImageParser(url)
                parser.feed(raw_html)
                return parser.image_url or parser.first_img
    except Exception:
        pass
    return None


class TrelloHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Keep console clean and lightweight

    def do_GET(self):
        if self.path == "/api/config":
            payload = {
                "supabaseUrl": os.environ.get("SUPABASE_URL", ""),
                "supabaseAnonKey": os.environ.get("SUPABASE_ANON_KEY", "")
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(DATA_FILE, "rb") as f:
                self.wfile.write(f.read())
            return

        if self.path.startswith("/api/preview?"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            target_url = params.get("url", [""])[0]
            image_url = extract_link_image(target_url) if target_url else None
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"image": image_url}).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        if self.path == "/api/data":
            try:
                parsed = json.loads(body.decode("utf-8"))
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, indent=2)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            return

        if self.path == "/api/upload-bg":
            try:
                payload = json.loads(body.decode("utf-8"))
                filename = re.sub(r"[^a-zA-Z0-9._-]", "_", payload.get("filename", "bg.jpg"))
                data_url = payload.get("data", "")
                if "," in data_url:
                    _, b64data = data_url.split(",", 1)
                    import base64
                    file_bytes = base64.b64decode(b64data)
                    save_path = os.path.join(UPLOADS_DIR, filename)
                    with open(save_path, "wb") as f:
                        f.write(file_bytes)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"url": f"/{UPLOADS_DIR}/{filename}"}).encode("utf-8"))
                    return
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
                return


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), TrelloHandler) as httpd:
        print(f"Local Trello running at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")