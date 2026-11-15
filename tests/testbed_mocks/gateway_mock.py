import http.server
import json
import socketserver
import threading
from typing import Optional, Tuple


class MockGatewayHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence HTTP server logs during pytest runs
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            # LiteLLM / OpenAI compatible models endpoint
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "object": "list",
                "data": [
                    {"id": "anthropic/claude-3-5-sonnet", "object": "model", "owned_by": "anthropic"},
                    {"id": "meta-llama/llama-3-70b-instruct", "object": "model", "owned_by": "meta"},
                ],
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif self.path == "/api/tags":
            # Ollama tags endpoint
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "models": [
                    {"name": "llama3:latest", "model": "llama3:latest"},
                    {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b"},
                ]
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ("/v1/chat/completions", "/v1/messages"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "id": "mock-resp-123",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "Mock gateway response"}}],
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class MockGatewayServer:
    def __init__(self, port: int = 0):
        self.server = socketserver.TCPServer(("127.0.0.1", port), MockGatewayHandler)
        self.port = self.server.server_address[1]
        self.thread: Optional[threading.Thread] = None

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
