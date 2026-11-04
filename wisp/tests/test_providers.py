"""Unit tests for the provider adapters: bodies, items, chunks, usage.

The openai-chat body must stay byte-identical to the pre-adapter
builder - that is the cache-prefix invariant for every existing
session, so the regression pins the current output. The same invariant
is pinned on text-only records in test_attachments.TestChatGoldenBody.
The other providers pin their wire shapes: item lists, tool specs,
auth headers, stream event mapping, and usage normalization.
"""

import io
import json
import os
import sys
import unittest

def _load_wisp():
    """Import ../wisp by file path under the module name wisp."""
    import importlib.machinery
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "wisp")
    loader = importlib.machinery.SourceFileLoader("wisp", path)
    spec = importlib.util.spec_from_loader("wisp", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


wisp = _load_wisp()


def _rec(kind, **kw):
    rec = {"type": kind}
    rec.update(kw)
    return rec


def _assistant(blocks, finish="stop"):
    return _rec("assistant", output=blocks, finish_reason=finish, usage=[])


RECORDS = [
    _rec("system", content="be terse"),
    _rec("user", content="hello"),
    _assistant([
        {"type": "reasoning", "text": "hm", "signature": "sig1",
         "encrypted_content": "enc1"},
        {"type": "text", "text": "hi"},
        {"type": "tool_call", "id": "c1", "name": "bash",
         "arguments": "{\"command\":\"echo x\"}"},
    ], finish="tool_calls"),
    _rec("tool", call_id="c1", name="bash", content="x", exit=0),
    _rec("user", content="and now?"),
    _assistant([
        {"type": "reasoning", "text": "old session block"},
        {"type": "text", "text": "done"},
    ]),
]


class _World:
    """A world with just what build_request and sse_stream read."""

    def __init__(self, api=None, thinking=None):
        self.world = wisp.World({})
        env = {"WISP_LLM_URL": "https://example.test",
               "WISP_LLM_API_KEY": "k"}
        if api:
            env["WISP_LLM_API"] = api
        self.world.set("env", env)
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("fs", _Fs())
        self.world.set("clock", _Clock())
        self.world.set("sessiondir", "/tmp")
        self.world.set("model", "m")
        self.world.set("thinking", thinking)


class _Fs:
    def append_text(self, path, text):
        pass


class _Clock:
    def ms(self):
        return 0


class TestBodies(unittest.TestCase):
    def test_responses_body(self):
        body = wisp.build_request(_World("openai-responses",
                                         thinking="low").world, RECORDS)
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["instructions"], "be terse")
        self.assertFalse(body["store"])
        self.assertTrue(body["stream"])
        self.assertEqual(body["reasoning"], {"effort": "low"})
        self.assertEqual(body["tools"][0]["name"], "bash")
        self.assertNotIn("function", body["tools"][0])
        items = body["input"]
        kinds = [i.get("type") or i.get("role") for i in items]
        self.assertEqual(kinds, [
            "user", "reasoning", "message", "function_call",
            "function_call_output", "user", "reasoning", "message"])
        # assistant text item
        self.assertEqual(items[2]["content"][0]["type"], "output_text")
        # signed reasoning replays its encrypted payload
        self.assertEqual(items[1]["encrypted_content"], "enc1")
        # the old-session unsigned reasoning replays as nothing
        self.assertNotIn("encrypted_content", items[6])
        # tool call keyed by stored id
        self.assertEqual(items[3]["call_id"], "c1")
        self.assertEqual(items[3]["name"], "bash")
        # tool output keyed the same way
        self.assertEqual(items[4]["call_id"], "c1")
        self.assertEqual(items[4]["output"], "x")

    def test_anthropic_body(self):
        world = _World("anthropic", thinking="high").world
        body = wisp.build_request(world, RECORDS)
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["system"], "be terse")
        self.assertEqual(body["max_tokens"], wisp.DEFAULT_MAX_TOKENS)
        self.assertEqual(body["tools"][0]["input_schema"]["type"], "object")
        self.assertEqual(body["thinking"]["type"], "enabled")
        self.assertGreaterEqual(body["thinking"]["budget_tokens"],
                                wisp.ANTHROPIC_MIN_BUDGET)
        # no unknown top-level field
        self.assertEqual(set(body) - {"model", "messages", "tools", "stream",
                                      "max_tokens", "system", "thinking"},
                         set())
        msgs = body["messages"]
        # signed thinking replays with signature
        self.assertEqual(msgs[1]["content"][0]["type"], "thinking")
        self.assertEqual(msgs[1]["content"][0]["signature"], "sig1")
        # unsigned old-session thinking drops (legal run-start removal)
        self.assertEqual([b["type"] for b in msgs[4]["content"]], ["text"])
        # tool_use input parses from the stored arguments JSON
        tu = [b for b in msgs[1]["content"] if b["type"] == "tool_use"][0]
        self.assertEqual(tu["input"], {"command": "echo x"})
        # tool result keyed by call_id, as a user message
        self.assertEqual(msgs[2]["role"], "user")
        self.assertEqual(msgs[2]["content"][0]["tool_use_id"], "c1")
        # two cache_control breakpoints: the last block of the last
        # message and of the message before it, moving forward as the
        # conversation grows
        marked = []
        for m in msgs:
            for b in m["content"]:
                if "cache_control" in b:
                    marked.append(b)
        self.assertEqual(len(marked), 2)
        self.assertEqual(marked[0], msgs[-2]["content"][-1])
        self.assertEqual(marked[1], msgs[-1]["content"][-1])

    def test_env_overrides(self):
        world = _World("anthropic", thinking="high").world
        world.get("env")["WISP_LLM_MAX_TOKENS"] = "77"
        world.get("env")["WISP_LLM_THINKING_BUDGET"] = "1"
        world.get("env")["WISP_LLM_ANTHROPIC_VERSION"] = "2023-06-01"
        body = wisp.build_request(world, RECORDS)
        self.assertEqual(body["max_tokens"], 77)
        self.assertEqual(body["thinking"]["budget_tokens"],
                         wisp.ANTHROPIC_MIN_BUDGET)
        headers = wisp.auth_headers_of(world, "anthropic")
        self.assertEqual(headers["x-api-key"], "k")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    def test_unknown_provider_fails(self):
        world = _World("nope").world
        with self.assertRaises(SystemExit) as caught:
            wisp.provider_of(world)
        self.assertEqual(caught.exception.code, 1)


class TestChunks(unittest.TestCase):
    def test_responses_events(self):
        out = wisp.responses_chunk_of
        self.assertIsNone(out({"type": "response.created"}))
        c = out({"type": "response.output_text.delta", "delta": "hi"})
        self.assertEqual(c["choices"][0]["delta"]["content"], "hi")
        c = out({"type": "response.reasoning_text.delta", "delta": "hm"})
        self.assertEqual(c["choices"][0]["delta"]["reasoning"], "hm")
        c = out({"type": "response.output_item.added", "output_index": 2,
                 "item": {"type": "function_call", "call_id": "c9",
                          "name": "bash"}})
        tc = c["choices"][0]["delta"]["tool_calls"][0]
        self.assertEqual((tc["index"], tc["id"], tc["function"]["name"]),
                         (2, "c9", "bash"))
        c = out({"type": "response.function_call_arguments.delta",
                 "output_index": 2, "delta": "{\"a\":"})
        self.assertEqual(c["choices"][0]["delta"]["tool_calls"][0]
                         ["function"]["arguments"], "{\"a\":")
        c = out({"type": "response.output_item.done", "output_index": 0,
                 "item": {"type": "reasoning",
                          "encrypted_content": "E"}})
        self.assertEqual(c["choices"][0]["delta"]["encrypted_content"], "E")
        c = out({"type": "response.completed", "response": {
            "output": [{"type": "function_call"}],
            "usage": {"input_tokens": 10, "output_tokens": 4,
                      "input_tokens_details": {"cached_tokens": 6}}}})
        self.assertEqual(c["choices"][0]["finish_reason"], "tool_calls")
        self.assertEqual(c["usage"]["prompt_tokens"], 10)
        self.assertEqual(c["usage"]["prompt_tokens_details"]
                         ["cached_tokens"], 6)

    def test_anthropic_events(self):
        out = wisp.anthropic_chunk_of
        self.assertIsNone(out({"type": "ping"}))
        self.assertIsNone(out({"type": "future_event"}))
        c = out({"type": "message_start", "message": {"usage": {
            "input_tokens": 3, "cache_read_input_tokens": 2,
            "cache_creation_input_tokens": 1}}})
        self.assertEqual(c["usage"]["prompt_tokens_details"]
                         ["cached_tokens"], 2)
        c = out({"type": "content_block_start", "index": 1,
                 "content_block": {"type": "tool_use", "id": "t9",
                                   "name": "bash"}})
        tc = c["choices"][0]["delta"]["tool_calls"][0]
        self.assertEqual((tc["index"], tc["id"], tc["function"]["name"]),
                         (1, "t9", "bash"))
        c = out({"type": "content_block_delta", "index": 0,
                 "delta": {"type": "text_delta", "text": "hi"}})
        self.assertEqual(c["choices"][0]["delta"]["content"], "hi")
        c = out({"type": "content_block_delta", "index": 0,
                 "delta": {"type": "thinking_delta", "thinking": "hm"}})
        self.assertEqual(c["choices"][0]["delta"]["reasoning"], "hm")
        c = out({"type": "content_block_delta", "index": 0,
                 "delta": {"type": "signature_delta", "signature": "s"}})
        self.assertEqual(c["choices"][0]["delta"]["signature"], "s")
        c = out({"type": "content_block_delta", "index": 1,
                 "delta": {"type": "input_json_delta",
                           "partial_json": "{\"a\":"}})
        self.assertEqual(c["choices"][0]["delta"]["tool_calls"][0]
                         ["function"]["arguments"], "{\"a\":")
        c = out({"type": "message_delta",
                 "delta": {"stop_reason": "tool_use"},
                 "usage": {"input_tokens": 3, "output_tokens": 2}})
        self.assertEqual(c["choices"][0]["finish_reason"], "tool_calls")

    def test_usage_normalizers(self):
        r = wisp.responses_usage_of({
            "input_tokens": 7, "output_tokens": 3,
            "input_tokens_details": {"cached_tokens": 5,
                                     "cache_write_tokens": 2},
            "output_tokens_details": {"reasoning_tokens": 1}})
        self.assertEqual(r, {
            "prompt_tokens": 7, "completion_tokens": 3,
            "total_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 5,
                                      "cache_write_tokens": 2},
            "completion_tokens_details": {"reasoning_tokens": 1}})
        self.assertIsNone(wisp.responses_usage_of(None))
        a = wisp.anthropic_usage_of({
            "input_tokens": 4, "output_tokens": 2,
            "cache_read_input_tokens": 9,
            "cache_creation_input_tokens": 8})
        self.assertEqual(a, {
            "prompt_tokens": 21, "completion_tokens": 2, "total_tokens": 23,
            "prompt_tokens_details": {"cached_tokens": 9,
                                      "cache_write_tokens": 8},
            "completion_tokens_details": {}})

    def test_turnacc_signatures(self):
        acc = wisp.TurnAcc(["reasoning_content", "reasoning", "thought"])
        acc.apply_delta({"choices": [{"delta": {"reasoning": "hm"}}]})
        acc.apply_delta({"choices": [{"delta": {"reasoning": " more"}}]})
        acc.apply_delta({"choices": [{"delta": {"signature": "s1"}}]})
        acc.apply_delta({"choices": [{"delta": {"reasoning": "second"}}]})
        acc.apply_delta({"choices": [{"delta": {"encrypted_content": "E"}}]})
        acc.apply_delta({"choices": [{"delta": {"content": "out"}}]})
        acc.apply_delta({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        self.assertEqual([b["type"] for b in acc.blocks],
                         ["reasoning", "reasoning", "text"])
        self.assertEqual(acc.blocks[0]["text"], "hm more")
        self.assertEqual(acc.blocks[0]["signature"], "s1")
        self.assertEqual(acc.blocks[1]["text"], "second")
        self.assertEqual(acc.blocks[1]["encrypted_content"], "E")


class TestSseStreamWiring(unittest.TestCase):
    def _run(self, api, lines):
        holder = _World(api)
        world = holder.world

        class _Http:
            def __init__(self):
                self.url = None
                self.headers = None

            def post_stream(self, url, headers, body, meta=None):
                self.url = url
                self.headers = headers
                for line in lines:
                    yield line

        http = _Http()
        world.set("http", http)
        self.last = (world, http)
        chunks = list(wisp.sse_stream(world, {"model": "m"}))
        return world, http, chunks

    def test_anthropic_route(self):
        world, http, chunks = self._run("anthropic", [
            "data: %s" % json.dumps({"type": "message_start", "message": {
                "usage": {"input_tokens": 1, "output_tokens": 0}}}),
            "data: %s" % json.dumps({"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta",
                                               "text": "hi"}}),
            "data: %s" % json.dumps({"type": "message_delta", "delta": {
                "stop_reason": "end_turn"}}),
            "data: [DONE]",
        ])
        self.assertEqual(http.url, "https://example.test/v1/messages")
        self.assertEqual(http.headers["x-api-key"], "k")
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[1]["choices"][0]["delta"]["content"], "hi")

    def test_responses_route(self):
        world, http, chunks = self._run("openai-responses", [
            "data: %s" % json.dumps({"type": "response.output_text.delta",
                                     "delta": "yo"}),
            "data: %s" % json.dumps({"type": "response.completed",
                                     "response": {"output": [], "usage": {
                                         "input_tokens": 1,
                                         "output_tokens": 1}}}),
        ])
        self.assertEqual(http.url, "https://example.test/v1/responses")
        self.assertEqual(http.headers["Authorization"], "Bearer k")
        self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "yo")

    def test_chat_route_unchanged(self):
        world, http, chunks = self._run("openai-chat", [
            "data: %s" % json.dumps({"choices": [{"delta": {
                "content": "x"}, "finish_reason": None}]}),
            "data: [DONE]",
        ])
        self.assertEqual(http.url, "https://example.test/v1/chat/completions")
        self.assertEqual(http.headers["Authorization"], "Bearer k")
        self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "x")

    def test_stream_error_fails(self):
        with self.assertRaises(SystemExit) as caught:
            self._run("anthropic", [
                "data: %s" % json.dumps({"type": "error", "error": {
                    "message": "overloaded"}}),
            ])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("overloaded", self.last[0].get("stderr").getvalue())
        self.assertEqual(caught.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
