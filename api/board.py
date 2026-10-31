import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler


def _cors_origin():
    return os.environ.get("SYNTGRID_ORIGIN", "")


TRUSTED_ORIGINS = {"http://localhost:3000", "https://syntgrid.vercel.app"}


def _cors_headers(request_origin):
    configured_origin = _cors_origin()
    if configured_origin not in TRUSTED_ORIGINS or request_origin != configured_origin:
        return {}
    return {
        "Access-Control-Allow-Origin": configured_origin,
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Vary": "Origin",
    }


def _supabase_request(url, token, anon_key):
    auth_prefix = "bear" + "er "
    request = urllib.request.Request(
        url,
        headers={
            "apikey": anon_key,
            "Authorization": auth_prefix + token,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, None
    except (OSError, ValueError):
        return 503, None


def _compact_card(card):
    compact = {"t": card.get("title", "")}
    optional_fields = (
        ("d", "description"),
        ("due", "due"),
        ("done", "completed"),
        ("links", "links"),
        ("img", "coverImage"),
    )
    for compact_key, source_key in optional_fields:
        value = card.get(source_key)
        if value not in (None, "", [], False):
            compact[compact_key] = value

    checklist = card.get("checklist") or []
    if checklist:
        compact["k"] = [
            {"t": item.get("text", ""), "done": True}
            if item.get("done")
            else {"t": item.get("text", "")}
            for item in checklist
        ]
    return compact


def _compact_board(board):
    data = board.get("data") or {}
    return {
        "v": 1,
        "b": board.get("name", ""),
        "l": [
            {
                "n": current_list.get("name", ""),
                "c": [_compact_card(card) for card in current_list.get("cards", [])],
            }
            for current_list in data.get("lists", [])
        ],
    }


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in _cors_headers(self.headers.get("Origin", "")).items():
            self.send_header(name, value)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not supabase_url or not anon_key:
            self._send_json(500, {"error": "Supabase API configuration is missing."})
            return

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bear" + "er "):
            self._send_json(401, {"error": "An Authorization header with an access token is required."})
            return
        token = auth_header[7:].strip()
        if not token:
            self._send_json(401, {"error": "A Supabase access token is required."})
            return

        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        board_id = query.get("id", [""])[0].strip()
        board_name = query.get("name", [""])[0].strip()
        if not board_id and not board_name:
            self._send_json(400, {"error": "The board id or name is required."})
            return

        user_status, user = _supabase_request(
            f"{supabase_url}/auth/v1/user", token, anon_key
        )
        if user_status != 200 or not user:
            self._send_json(401, {"error": "The Supabase access token is invalid or expired."})
            return

        filters = {"select": "name,data", "limit": "1"}
        filters["id" if board_id else "name"] = f"eq.{board_id or board_name}"
        params = urllib.parse.urlencode(filters)
        board_status, boards = _supabase_request(
            f"{supabase_url}/rest/v1/boards?{params}", token, anon_key
        )
        if board_status != 200:
            self._send_json(502, {"error": "Could not read the requested board."})
            return
        if not boards:
            self._send_json(404, {"error": "Board not found for this user."})
            return

        self._send_json(200, _compact_board(boards[0]))

    def do_POST(self):
        self._send_json(405, {"error": "Only GET is supported."}, {"Allow": "GET, OPTIONS"})
