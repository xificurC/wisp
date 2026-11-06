#!/usr/bin/env python3
"""One-shot fake LLM endpoint for wisp run tests.

Serves POST /v1/chat/completions. The default mode serves a fixed SSE
stream for every request: one text delta, one stop finish, [DONE].
Mode tworound serves round one as one bash tool call and every later
round as a final stop answer, so a two-round turn commits twice.
Mode hang serves round one as one bash tool call and never answers
round two: the second request sleeps, so a test can kill the wisp run
process mid-turn after round one committed. Mode json serves one
non-stream chat.completion body: text plus usage. Mode json_two serves
round one as two non-stream tool calls and every later round as a
final text answer plus usage; both json modes answer 400 with the
proxy's stream refusal when the request body says stream: true, so the
non-stream body gate stays pinned. Serves GET /v1/model/info with an
empty table. Writes each POST body to $FAKE_LLM_CAPTURE, one JSON line
per request, when that env is set. Binds port 0 when PORT is 0 or
absent, prints the chosen port on one stdout line, and serves after
that line. No fixed ports. Usage: fake_llm_sse.py [PORT] [MODE]. Runs
until killed.
"""
import http.server
import json
import os
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


STREAM_REFUSED = ("stream is not supported by this proxy;"
                  " remove :stream from the features")


def chat_body(message, finish_reason, usage):
    """One non-stream chat.completion body."""
    return {"id": "chatcmpl-fake", "object": "chat.completion",
            "choices": [{"index": 0, "message": message,
                         "finish_reason": finish_reason}],
            "usage": usage}


def json_round(count):
    """One non-stream body: text plus usage."""
    return chat_body({"role": "assistant",
                      "content": "the fake final answer"}, "stop", USAGE)


def json_two_round(count):
    """Round one carries two tool calls; later rounds a text answer."""
    if count == 1:
        return chat_body({"role": "assistant", "content": None,
                          "tool_calls": [
                              {"id": "call_1", "type": "function",
                               "function": {
                                   "name": "bash",
                                   "arguments": json.dumps(
                                       {"command": "echo first-call"})}},
                              {"id": "call_2", "type": "function",
                               "function": {
                                   "name": "bash",
                                   "arguments": json.dumps(
                                       {"command": "echo second-call"})}},
                          ]}, "tool_calls", USAGE)
    return json_round(count)


USAGE = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18,
         "prompt_tokens_details": {"cached_tokens": 3}}

MODES = {"default": default_stream,
         "tworound": tworound_stream,
         "stopcall": stopcall_stream,
         "hang": hang_stream}
JSON_MODES = {"json": json_round, "json_two": json_two_round}
REQUEST_COUNT = [0]


class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        capture = os.environ.get("FAKE_LLM_CAPTURE")
        if capture:
            with open(capture, "ab") as handle:
                handle.write(raw + b"\n")
        REQUEST_COUNT[0] += 1
        if mode in JSON_MODES:
            try:
                want_stream = bool(json.loads(raw.decode("utf-8", "replace"))
                                   .get("stream"))
            except (ValueError, AttributeError):
                want_stream = False
            if want_stream:
                body = json.dumps(
                    {"error": {"message": STREAM_REFUSED}}).encode("utf-8")
                self.respond(400, "application/json", body)
                return
            body = json.dumps(JSON_MODES[mode](REQUEST_COUNT[0]),
                              ensure_ascii=False).encode("utf-8")
            self.respond(200, "application/json", body)
            return
        body = MODES[mode](REQUEST_COUNT[0])
        if not body:
            return
        self.respond(200, "text/event-stream", body)

    def do_GET(self):
        self.respond(200, "application/json", b'{"data":[]}')

    def log_message(self, *args):
        pass


args = sys.argv[1:]
port = 0
mode = "default"
if args and args[0].isdigit():
    port = int(args.pop(0))
if args:
    mode = args.pop(0)
if (mode not in MODES and mode not in JSON_MODES) or args:
    print("fake_llm_sse.py: unknown arguments: %s" % " ".join(sys.argv[1:]),
          file=sys.stderr)
    sys.exit(2)
server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
