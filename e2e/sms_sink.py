"""Loopback-only in-memory SMS capture used by the Playwright test environment."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


messages: dict[str, str] = {}


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:14173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            payload = {"status": "ok"}
        elif parsed.path == "/messages":
            phone = parse_qs(parsed.query).get("phone", [""])[0]
            message = messages.get(phone)
            if message is None:
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            payload = {"message": message}
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        body = json.dumps(payload).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/messages":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            phone = payload["phone"]
            message = payload["message"]
            if not isinstance(phone, str) or not isinstance(message, str):
                raise ValueError("Invalid SMS payload")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_response(400)
            self._cors()
            self.end_headers()
            return

        messages[phone] = message
        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, _format: str, *_args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18890)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
