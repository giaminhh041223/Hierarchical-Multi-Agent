"""Offline checks: no inference, accounts or real keys are used."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

import adapters


class _Handler(BaseHTTPRequestHandler):
    hits = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        self.hits.append(self.path)
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/redirect":
            self.send_response(307)
            self.send_header("Location", "/stolen")
            self.end_headers()
        elif self.path == "/error":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"DO_NOT_LEAK_secret")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')


class AdapterTests(unittest.TestCase):
    def test_transport_never_follows_authenticated_redirects_or_exposes_error_body(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with self.assertRaises(adapters.AdapterError):
                adapters._post(base + "/redirect", {}, {"Authorization": "Bearer fake-test-key"})
            self.assertNotIn("/stolen", _Handler.hits)
            with self.assertRaises(adapters.AdapterError) as failure:
                adapters._post(base + "/error", {}, {"Authorization": "Bearer fake-test-key"})
            self.assertNotIn("DO_NOT_LEAK", str(failure.exception))
            self.assertNotIn("fake-test-key", str(failure.exception))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_endpoint_and_model_boundaries(self):
        for endpoint in ("http://example.com", "https://user:password@example.com", "https://example.com?key=abc", "https://example.com\n"):
            with self.assertRaises(adapters.AdapterError):
                adapters._endpoint(endpoint, "/api")
        with patch.object(adapters, "_run") as run:
            for model in ("--dangerously-bypass-approvals-and-sandbox", "model\nexec", "model;calc"):
                with self.assertRaises(adapters.AdapterError):
                    adapters.execute("codex", model, "test", Path.cwd())
            run.assert_not_called()

    def test_codex_requires_terminal_success_and_reports_usage(self):
        records = [{"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
                   {"type": "turn.completed", "usage": {"input_tokens": 9, "output_tokens": 3}}]
        with patch.object(adapters, "_command", return_value=["codex.exe"]), patch.object(adapters, "_run", return_value="\n".join(map(json.dumps, records))) as run:
            result = adapters.execute("codex", "chosen-model", "test", Path.cwd())
            self.assertEqual((result["text"], result["input_tokens"], result["output_tokens"]), ("done", 9, 3))
            self.assertIn("workspace-write", run.call_args.args[0])
            run.return_value = json.dumps(records[0])
            with self.assertRaises(adapters.AdapterError):
                adapters.execute("codex", "chosen-model", "test", Path.cwd())

    def test_timeout_and_cancellation_stop_cli(self):
        with self.assertRaisesRegex(adapters.AdapterError, "quá thời gian"):
            adapters._run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
        event = threading.Event()
        timer = threading.Timer(0.15, event.set)
        timer.start()
        try:
            with self.assertRaisesRegex(adapters.AdapterError, "đã hủy"):
                adapters._run([sys.executable, "-c", "import time; time.sleep(30)"], cancel_event=event)
        finally:
            timer.cancel()

    def test_api_shapes_without_credentials_or_network(self):
        samples = {
            "openai_compatible": {"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}], "usage": {"prompt_tokens": 4, "completion_tokens": 1}},
            "anthropic": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "OK"}], "usage": {"input_tokens": 4, "output_tokens": 1}},
            "gemini": {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "OK"}]}}], "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 1}},
        }
        for provider, payload in samples.items():
            with self.subTest(provider=provider), patch.object(adapters, "_post", return_value=payload):
                result = adapters.execute(provider, "chosen-model", "test", Path.cwd(), key="fake-test-key")
                self.assertEqual((result["text"], result["input_tokens"], result["output_tokens"]), ("OK", 4, 1))


if __name__ == "__main__":
    unittest.main()
