#!/usr/bin/env python3
"""Tiny OpenAI-compatible mock used by the CI smoke test.

Speaks just enough of the OpenAI chat-completions API -- SSE streaming for
``stream=True`` requests and a plain JSON completion otherwise -- so the app's
real LangChain/OpenRouter pipeline can run end-to-end without reaching
OpenRouter. It always answers with a canned, grounded-sounding reply.

Point the app at it with ``OPENROUTER_API_BASE=http://host:8090/v1`` (the
langchain-openrouter SDK reads that variable itself) and a dummy
``OPENROUTER_API_KEY``.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = 8090

CHUNKS = [
    "بر اساس سند [1]، ",
    "فروش سه‌ماهه اول امسال نسبت به دوره مشابه رشد داشته است. ",
    "\n\nمنابع:\n[1] گزارش فروش سه ماهه اول 1403",
]

ANSWER = "".join(CHUNKS)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/v1/models":
            self._send_json(
                {"object": "list", "data": [{"id": "mock-model", "object": "model"}]}
            )
        else:
            self._send_json({"error": {"message": "not found"}}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/v1/chat/completions":
            self._send_json({"error": {"message": "not found"}}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}
        if body.get("stream"):
            self._send_sse()
        else:
            self._send_json(self._completion_body())

    def _completion_body(self):
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ANSWER},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _send_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for index, text in enumerate(CHUNKS):
            delta = (
                {"role": "assistant", "content": text}
                if index == 0
                else {"content": text}
            )
            event = {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "mock-model",
                "choices": [
                    {"index": 0, "delta": delta, "finish_reason": None}
                ],
            }
            self.wfile.write(
                f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
            )
            self.wfile.flush()
            time.sleep(0.01)
        final = {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "mock-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self.wfile.write(
            f"data: {json.dumps(final, ensure_ascii=False)}\n\n".encode("utf-8")
        )
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()