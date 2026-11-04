"""Unit tests for the wisp.log observability events.

Every event that runs outside the normal turn flow - process exit,
crashes, HTTP errors - must leave one wisp.log line, so a dead run
can be told apart from a slow endpoint, a firewall block, or a wisp
fault. This pins the line formats: request/response/cache/commit and
tool start/end through loop_rounds; http post/done through a fake
http stream; http_error and streamfail on the two failure branches;
safe_log itself never raises, so observability cannot turn one
clean failure into a second one. The extensionless wisp module
imports by path, so the package stays stdlib only."""
import email.message
import io
import json
import os
import sys
import tempfile
import unittest

import importlib.machinery
import importlib.util


def _load_wisp():
    """Import ../wisp by file path under the module name wisp."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "wisp")
    loader = importlib.machinery.SourceFileLoader("wisp", path)
    spec = importlib.util.spec_from_loader("wisp", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


wisp = _load_wisp()


def _tool_call(cid="c1"):
    return {"type": "tool_call", "id": cid, "name": "bash",
            "arguments": "{\"command\":\"echo x\"}"}


def _tool(cid="c1"):
    return {"type": "tool", "call_id": cid, "name": "bash",
            "content": "x", "exit": 0}


class _Llm:
    """Scripted turns; logs sit in the real loop, not here."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def turn(self, records):
        self.calls += 1
        t = self.turns.pop(0)
        return {"finish_reason": t[1], "cached_tokens": 0,
                "assistant": {"type": "assistant", "output": list(t[0]),
                              "finish_reason": t[1], "usage": []}}


class _Stdin:
    def read_text(self):
        raise AssertionError("loop_rounds reads no stdin")


class _FakeHttp:
    """post_stream yields scripted lines, or raises once."""

    def __init__(self, lines=None, error=None, status=None, request_id=""):
        self.lines = lines or []
        self.error = error
        self.status = status
        self.request_id = request_id
        self.posts = []

    def post_stream(self, url, headers, body, meta=None):
        self.posts.append((url, body))
        if meta is not None:
            if self.status is not None:
                meta["status"] = self.status
            if self.request_id:
                meta["request_id"] = self.request_id
        if self.error:
            raise self.error
        for line in self.lines:
            yield line


class _Response:
    """One scripted urlopen response: status, headers, body lines."""

    def __init__(self, lines, status=200, headers=None):
        self.lines = lines
        self.status = status
        self.headers = headers or {}
        self.closed = False

    def __iter__(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False


class _Harness:
    """One session dir plus a world wired for loop_rounds/sse_stream."""

    def __init__(self, http=None):
        self._temp = tempfile.TemporaryDirectory()
        self.sessiondir = os.path.join(self._temp.name, "run")
        os.makedirs(self.sessiondir)
        for name in ("wisp.jsonl", "wisp.usage"):
            with open(os.path.join(self.sessiondir, name), "w") as h:
                h.write("")
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("stdin", _Stdin())
        self.http = http or _FakeHttp()
        self.world.set("http", self.http)
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "http://u",
                               "WISP_LLM_API_KEY": "k"})
        self.world.set("model", "m")
        self.world.set("thinking", None)
        self.world.set("committed", 0)
        self.llm = _Llm([])
        self.world.set("llm", self.llm)
        # the real Tools service and executor: the tool start/end
        # log lines are their code under test, and `echo x` is a
        # real subprocess
        self.world.set("exec", wisp.Executor(self.world))
        self.world.set("tools", wisp.Tools(self.world))

    def set_http(self, fake):
        self.http = fake
        self.world.set("http", fake)

    def run(self, turns, max_rounds=10):
        self.llm = _Llm(turns)
        self.world.set("llm", self.llm)
        records = [{"type": "user", "content": "turn"}]
        wisp.loop_rounds(self.world, records, max_rounds, None)
        return records

    def log_lines(self, event):
        path = os.path.join(self.sessiondir, "wisp.log")
        if not os.path.exists(path):
            return []
        with open(path) as h:
            return [ln for ln in h.read().splitlines()
                    if ln.split(" ", 2)[1] == event]

    def close(self):
        self._temp.cleanup()


class ObservabilityTest(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()

    def tearDown(self):
        self.h.close()

    def test_turn_flow_lines(self):
        """One tool turn and one text turn leave the full event chain."""
        self.h.run([([{"type": "reasoning", "text": "t"},
                      _tool_call()], "tool_calls"),
                    ([{"type": "text", "text": "done"}], "stop")])
        lines = {e: self.h.log_lines(e) for e in
                 ("request", "response", "cache", "commit",
                  "tool", "retry")}
        self.assertEqual(len(lines["request"]), 2)
        self.assertIn("model=m", lines["request"][0])
        self.assertIn("api=openai-chat", lines["request"][0])
        self.assertIn("round=1", lines["request"][0])
        self.assertEqual(len(lines["response"]), 2)
        self.assertIn("finish_reason=tool_calls", lines["response"][0])
        self.assertEqual(len(lines["cache"]), 2)
        self.assertIn("cached_tokens=0", lines["cache"][0])
        # the loop commits after each round: the tool round and
        # the final text turn
        self.assertEqual(len(lines["commit"]), 2)
        self.assertIn("records=3", lines["commit"][0])
        self.assertIn("records=1", lines["commit"][1])
        self.assertEqual(len(lines["retry"]), 0)
        tool = [ln for ln in lines["tool"] if " start " in ln + " "]
        # tool start and end lines exist with call_id and exit fields
        starts = [ln for ln in lines["tool"] if "call_id=c1" in ln
                  and "name=bash" in ln]
        self.assertEqual(len(starts), 2)
        ends = [ln for ln in starts if "exit=" in ln]
        self.assertEqual(len(ends), 1)
        self.assertIn("ms=", ends[0])

    def test_http_done_line(self):
        """A clean stream logs http post and http_done with counts."""
        chunk = json.dumps({"choices": [{"delta": {}}]})
        self.h.http.lines = ["data: " + chunk, "data: [DONE]"]
        payloads = list(wisp.sse_stream(self.h.world, {"model": "m"}))
        self.assertEqual(len(payloads), 1)
        post = self.h.log_lines("http")
        self.assertEqual(len(post), 1)
        self.assertIn("url=http://u/v1/chat/completions", post[0])
        self.assertIn("bytes=", post[0])
        done = self.h.log_lines("http_done")
        self.assertEqual(len(done), 1)
        self.assertIn("lines=2", done[0])
        self.assertIn("payloads=1", done[0])
        self.assertIn("ms=", done[0])
        self.assertEqual(self.h.log_lines("http_error"), [])
        self.assertEqual(self.h.log_lines("streamfail"), [])

    def test_http_error_line(self):
        """A raised HttpError logs one http_error line, then raises."""
        self.h.set_http(_FakeHttp(error=wisp.HttpError("500 boom")))
        with self.assertRaises(wisp.HttpError):
            list(wisp.sse_stream(self.h.world, {"model": "m"}))
        err = self.h.log_lines("http_error")
        self.assertEqual(len(err), 1)
        self.assertIn("url=http://u/v1/chat/completions", err[0])
        self.assertIn("err=500 boom", err[0])
        self.assertIn("ms=", err[0])
        self.assertEqual(self.h.log_lines("http_done"), [])

    def test_streamfail_line(self):
        """A body with no choices payload logs streamfail, then exits."""
        self.h.set_http(_FakeHttp(lines=["data: {\"error\": \"bad\"}"]))
        with self.assertRaises(SystemExit) as caught:
            list(wisp.sse_stream(self.h.world, {"model": "m"}))
        self.assertEqual(caught.exception.code, 1)
        bad = self.h.log_lines("streamfail")
        self.assertEqual(len(bad), 1)
        self.assertIn("lines=1", bad[0])
        self.assertIn("payloads=0", bad[0])
        self.assertIn("first=", bad[0])

    def test_empty_sse_stream_is_a_retryable_empty_turn(self):
        """A stream with data lines but no choices is not a hard
        failure: sse_stream ends quietly and names the cause."""
        self.h.set_http(_FakeHttp(lines=["", "data: {}"]))
        payloads = list(wisp.sse_stream(self.h.world, {"model": "m"}))
        self.assertEqual(payloads, [])
        bad = self.h.log_lines("streamfail")
        self.assertEqual(len(bad), 1)
        self.assertIn("lines=2", bad[0])
        self.assertIn("payloads=0", bad[0])
        self.assertIn("sse=yes", bad[0])
        self.assertIn("no completion payload",
                      self.h.world.get("stream_note"))

    def test_non_sse_body_still_fails(self):
        """A body with no data line is not a stream: it fails at once."""
        self.h.set_http(_FakeHttp(lines=["<html>oops</html>"]))
        with self.assertRaises(SystemExit) as caught:
            list(wisp.sse_stream(self.h.world, {"model": "m"}))
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("sse=no", self.h.log_lines("streamfail")[0])

    def test_http_done_line_carries_status_and_request_id(self):
        """The status and request id ride the done line."""
        chunk = json.dumps({"choices": [{"delta": {}}]})
        self.h.http.lines = ["data: " + chunk, "data"]
        self.h.http.status = 200
        self.h.http.request_id = "req-42"
        list(wisp.sse_stream(self.h.world, {"model": "m"}))
        done = self.h.log_lines("http_done")[0]
        self.assertIn("status=200", done)
        self.assertIn("reqid=req-42", done)

    def test_streamfail_line_carries_status_and_request_id(self):
        """The empty stream fail line and note name the request."""
        self.h.http.lines = ["data: x"]
        self.h.http.status = 200
        self.h.http.request_id = "req-42"
        list(wisp.sse_stream(self.h.world, {"model": "m"}))
        bad = self.h.log_lines("streamfail")[0]
        self.assertIn("status=200", bad)
        self.assertIn("reqid=req-42", bad)
        note = self.h.world.get("stream_note")
        self.assertIn("request id: req-42", note)

    def test_http_error_line_carries_status_and_request_id(self):
        """The transport fail line names the request too."""
        boom = wisp.HttpError("500 boom")
        self.h.set_http(_FakeHttp(error=boom))
        self.h.http.status = 500
        self.h.http.request_id = "req-err"
        with self.assertRaises(wisp.HttpError):
            list(wisp.sse_stream(self.h.world, {"model": "m"}))
        line = self.h.log_lines("http_error")[0]
        self.assertIn("status=500", line)
        self.assertIn("reqid=req-err", line)

    def test_safe_log_never_raises(self):
        """safe_log drops the line when the session service is absent."""
        empty = wisp.World({})
        wisp.safe_log(empty, "crash", "err=x")  # must not raise
        broken = wisp.World({})
        broken.set("session", None)
        broken.set("fs", None)
        wisp.safe_log(broken, "exit", "rc=0")  # must not raise


class RequestIdHeaderTest(unittest.TestCase):
    """The request id header names the request in the proxy log."""

    def test_known_names_win_in_order(self):
        h = wisp.request_id_of_headers
        self.assertEqual(h({"x-request-id": "a"}), "a")
        self.assertEqual(h({"X-LiteLLM-Request-Id": "b"}), "b")

    def test_any_request_id_suffix_is_a_fallback(self):
        h = wisp.request_id_of_headers
        self.assertEqual(h({"x-vendor-request-id": "c"}), "c")

    def test_no_header_gives_empty(self):
        h = wisp.request_id_of_headers
        self.assertEqual(h({}), "")
        self.assertEqual(h(None), "")

    def test_post_stream_fills_meta_before_first_line(self):
        seen = {}

        def fake(request, timeout=None):
            return _Response([b"data: x\n"], headers={"X-Request-Id": "req-7"})
        real = wisp.urllib.request.urlopen
        wisp.urllib.request.urlopen = fake
        try:
            http = wisp.Http(wisp.World({}))
            lines = list(http.post_stream("http://u", {}, {}, seen))
        finally:
            wisp.urllib.request.urlopen = real
        self.assertEqual(lines, ["data: x"])
        self.assertEqual(seen, {"status": 200, "request_id": "req-7"})

    def test_post_stream_fills_meta_on_an_http_error(self):
        seen = {}

        def fake(request, timeout=None):
            hdrs = {"x-litellm-request-id": "req-500"}
            raise wisp.urllib.error.HTTPError(
                "http://u", 500, "boom", hdrs,
                io.BytesIO(b"down"))
        real = wisp.urllib.request.urlopen
        wisp.urllib.request.urlopen = fake
        try:
            with self.assertRaises(wisp.HttpError):
                http = wisp.Http(wisp.World({}))
                list(http.post_stream("http://u", {}, {}, seen))
        finally:
            wisp.urllib.request.urlopen = real
        self.assertEqual(seen, {"status": 500, "request_id": "req-500"})

    def test_email_message_headers_work(self):
        """Real urllib headers are an email Message, not a dict."""
        hdrs = email.message.Message()
        hdrs["X-Request-Id"] = "req-msg"
        self.assertEqual(wisp.request_id_of_headers(hdrs), "req-msg")


if __name__ == "__main__":
    unittest.main()
