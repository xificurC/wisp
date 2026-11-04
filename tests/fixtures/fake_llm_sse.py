#!/usr/bin/env python3
"""One-shot fake LLM endpoint for wisp run tests.

Serves POST /v1/chat/completions. The default mode serves a fixed SSE
stream for every request: one text delta, one stop finish, [DONE].
Mode tworound serves round one as one bash tool call and every later
round as a final stop answer, so a two-round turn commits twice.
Mode hang serves round one as one bash tool call and never answers
round two: the second request sleeps, so a test can kill the wisp run
process mid-turn after round one committed. Serves GET /v1/model/info
with an empty table. Binds port 0 when PORT is 0 or absent, prints the
chosen port on one stdout line, and serves after that line. No fixed
ports. Usage: fake_llm_sse.py [PORT] [MODE]. Runs until killed.
"""
import http.server
import json
import sys
import time

SSE = (b'data: {"choices":[{"delta":{"content":"the child answer"}}]}\n\n'
       b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
       b'data: [DONE]\n\n')


def sse_bytes(*chunks):
    """One mode stream: chunk payloads as `data:` lines, then [DONE]."""
    text = "".join("data: %s\n\n" % json.dumps(chunk, ensure_ascii=False)
                   for chunk in chunks) + "data: [DONE]\n\n"
    return text.encode("utf-8")


TOOL_CALL_ROUND = sse_bytes(
    {"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": "call_1", "type": "function",
        "function": {"name": "bash",
                     "arguments": json.dumps(
                         {"command": "echo committed-round-one"})},
    }]}}]},
    {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})

FINAL_STOP_ROUND = sse_bytes(
    {"choices": [{"delta": {"content": "the fake final answer"}}]},
    {"choices": [{"delta": {}, "finish_reason": "stop"}]})


def default_stream(count):
    """The original one-shot behavior, request order aside."""
    return SSE


def tworound_stream(count):
    """Round one is one bash tool call; later rounds are a stop answer."""
    return TOOL_CALL_ROUND if count == 1 else FINAL_STOP_ROUND


def stopcall_stream(count):
    """Round one carries tool-call deltas but ends with finish_reason
    stop - the premature-end shape some endpoints produce. Later
    rounds are a stop answer."""
    if count == 1:
        return sse_bytes(
            {"choices": [{"delta": {"tool_calls": [{
                "index": 0, "id": "call_1", "type": "function",
                "function": {"name": "bash",
                             "arguments": json.dumps(
                                 {"command": "echo stop-call-round"})},
            }]}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]})
    return FINAL_STOP_ROUND


def hang_stream(count):
    """Round one is one bash tool call; round two never answers."""
    if count == 1:
        return TOOL_CALL_ROUND
    time.sleep(600)  # the stream never arrives; the test kills the run
    return b""


MODES = {"default": default_stream,
         "tworound": tworound_stream,
         "stopcall": stopcall_stream,
         "hang": hang_stream}
REQUEST_COUNT = [0]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        REQUEST_COUNT[0] += 1
        body = MODES[mode](REQUEST_COUNT[0])
        if not body:
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        body = b'{"data":[]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


args = sys.argv[1:]
port = 0
mode = "default"
if args and args[0].isdigit():
    port = int(args.pop(0))
if args:
    mode = args.pop(0)
if mode not in MODES or args:
    print("fake_llm_sse.py: unknown arguments: %s" % " ".join(sys.argv[1:]),
          file=sys.stderr)
    sys.exit(2)
server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
