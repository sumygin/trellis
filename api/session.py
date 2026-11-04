import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler


TRUSTED_ORIGINS = {"http://localhost:3000", "https://syntgrid.vercel.app"}


def _cors_headers(request_origin):
    configured_origin = os.environ.get("SYNTGRID_ORIGIN", "")
    if configured_origin not in TRUSTED_ORIGINS or request_origin != configured_origin:
        return {}
    return {
        "Access-Control-Allow-Origin": configured_origin,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Vary": "Origin",
    }


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in _cors_headers(self.headers.get("Origin", "")).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_POST(self):
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid JSON."})
            return

        refresh_token = body.get("refreshToken") if isinstance(body, dict) else None
        if not supabase_url or not anon_key:
            self._send_json(500, {"error": "Supabase API configuration is missing."})
            return
        if not isinstance(refresh_token, str) or not refresh_token:
            self._send_json(400, {"error": "A refresh token is required."})
            return

        request = urllib.request.Request(
            f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
            data=urllib.parse.urlencode({"refresh_token": refresh_token}).encode("utf-8"),
            headers={
                "apikey": anon_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                session = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            self._send_json(401, {"error": "The Trellis session has expired. Relink Trellis."})
            return
        except (OSError, ValueError):
            self._send_json(503, {"error": "Could not refresh the Trellis session."})
            return

        self._send_json(200, {
            "accessToken": session.get("access_token"),
            "refreshToken": session.get("refresh_token", refresh_token),
        })
