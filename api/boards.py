import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler


def _supabase_request(url, token, anon_key):
    request = urllib.request.Request(
        url,
        headers={"apikey": anon_key, "Authorization": "bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, OSError, ValueError):
        return 503, None


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", os.environ.get("SYNTGRID_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
        authorization = self.headers.get("Authorization", "")
        if not supabase_url or not anon_key:
            self._send_json(500, {"error": "Supabase API configuration is missing."})
            return
        if not authorization.lower().startswith("bearer "):
            self._send_json(401, {"error": "A Supabase access token is required."})
            return
        token = authorization[7:].strip()
        user_status, user = _supabase_request(f"{supabase_url}/auth/v1/user", token, anon_key)
        if user_status != 200 or not user or not user.get("id"):
            self._send_json(401, {"error": "The Supabase access token is invalid or expired."})
            return
        query = urllib.parse.urlencode({
            "select": "id,name,board_members!inner(role)",
            "board_members.user_id": f"eq.{user['id']}",
            "order": "name.asc",
        })
        status, boards = _supabase_request(f"{supabase_url}/rest/v1/boards?{query}", token, anon_key)
        if status != 200 or not isinstance(boards, list):
            self._send_json(502, {"error": "Could not read accessible Trellis boards."})
            return
        self._send_json(200, {
            "boards": [
                {
                    "id": board.get("id"),
                    "name": board.get("name"),
                    "role": (board.get("board_members") or [{}])[0].get("role", "viewer"),
                }
                for board in boards
            ]
        })

