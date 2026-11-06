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
import tempfile
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


URL_OF = {
    "openai-chat": "https://example.test/v1/chat/completions",
    "openai-responses": "https://example.test/v1/responses",
    "anthropic": "https://example.test/v1/messages",
}


class _World:
    """A world with just what build_request and sse_stream read."""

    def __init__(self, api=None, thinking=None):
        self.world = wisp.World({})
        env = {"WISP_LLM_URL": URL_OF.get(api or "openai-chat",
                                          URL_OF["openai-chat"]),
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
        self.assertEqual(body["include"], ["reasoning.encrypted_content"])
        self.assertEqual(body["reasoning"],
                         {"effort": "low", "summary": "auto"})
        self.assertEqual(body["prompt_cache_key"], "tmp")
        self.assertEqual(body["tools"][0]["name"], "bash")
        self.assertNotIn("function", body["tools"][0])
        items = body["input"]
        kinds = [i.get("type") or i.get("role") for i in items]
        self.assertEqual(kinds, [
            "user", "reasoning", "message", "function_call",
            "function_call_output", "user", "reasoning", "message"])
        # assistant text item
        self.assertEqual(items[2]["content"][0]["type"], "output_text")
        # signed reasoning replays its summary and its encrypted payload
        self.assertEqual(items[1]["summary"],
                         [{"type": "summary_text", "text": "hm"}])
        self.assertEqual(items[1]["encrypted_content"], "enc1")
        # the old-session unsigned reasoning replays its summary only
        self.assertEqual(items[6]["summary"],
                         [{"type": "summary_text",
                           "text": "old session block"}])
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
        self.assertEqual(body["thinking"], {"type": "adaptive"})
        self.assertEqual(body["output_config"], {"effort": "high"})
        # no unknown top-level field
        self.assertEqual(set(body) - {"model", "messages", "tools", "stream",
                                      "max_tokens", "system", "thinking",
                                      "output_config"},
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
        body = wisp.build_request(world, RECORDS)
        self.assertEqual(body["max_tokens"], 77)
        self.assertEqual(body["output_config"], {"effort": "high"})

    def test_anthropic_thinking_level_rides_effort(self):
        for level in ("low", "medium", "high", "xhigh", "max"):
            body = wisp.build_request(
                _World("anthropic", thinking=level).world, RECORDS)
            self.assertEqual(body["thinking"], {"type": "adaptive"})
            self.assertEqual(body["output_config"], {"effort": level})
            self.assertNotIn("budget_tokens", body["thinking"])

    def test_anthropic_without_thinking_sends_no_thinking_keys(self):
        body = wisp.build_request(_World("anthropic").world, RECORDS)
        self.assertNotIn("thinking", body)
        self.assertNotIn("output_config", body)

    def test_extra_headers_carry_the_version(self):
        world = _World("anthropic").world
        world.get("env")["WISP_LLM_HEADERS"] = json.dumps(
            {"anthropic-version": "2026-10-21"})
        headers = wisp.auth_headers_of(world)
        self.assertEqual(headers["anthropic-version"], "2026-10-21")
        self.assertEqual(headers["Authorization"], "Bearer k")
        self.assertNotIn("x-api-key", headers)

    def test_extra_headers_env(self):
        world = _World("openai-chat").world
        world.get("env")["WISP_LLM_HEADERS"] = json.dumps({
            "x-opencode-session": "{session}",
            "User-Agent": "wisp/test"})
        headers = wisp.auth_headers_of(world)
        self.assertEqual(headers["x-opencode-session"], "tmp")
        self.assertEqual(headers["User-Agent"], "wisp/test")
        self.assertEqual(headers["Authorization"], "Bearer k")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["User-Agent"], "wisp/test")

    def test_client_names_itself(self):
        headers = wisp.auth_headers_of(_World("openai-chat").world)
        self.assertEqual(headers["User-Agent"], "wisp")

    def test_extra_headers_match_case_insensitively(self):
        world = _World().world
        world.get("env")["WISP_LLM_HEADERS"] = '{"authorization": "Bearer x"}'
        headers = wisp.auth_headers_of(world)
        self.assertEqual(headers["authorization"], "Bearer x")
        self.assertNotIn("Authorization", headers)

    def test_extra_headers_null_deletes(self):
        world = _World().world
        world.get("env")["WISP_LLM_HEADERS"] = '{"Authorization": null}'
        world.get("env")["WISP_LLM_API_KEY"] = ""
        headers = wisp.auth_headers_of(world)
        self.assertNotIn("Authorization", headers)

    def test_extra_headers_take_the_key(self):
        world = _World().world
        world.get("env")["WISP_LLM_HEADERS"] = '{"X-Api-Key": "{key}"}'
        world.get("env")["WISP_LLM_API_KEY"] = "secret"
        headers = wisp.auth_headers_of(world)
        self.assertEqual(headers["X-Api-Key"], "secret")
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_missing_key_fails_only_on_a_surviving_placeholder(self):
        world = _World().world
        world.get("env")["WISP_LLM_API_KEY"] = ""
        with self.assertRaises(SystemExit) as caught:
            wisp.auth_headers_of(world)
        self.assertEqual(caught.exception.code, 1)
        world.get("env")["WISP_LLM_HEADERS"] = '{"Authorization": "local"}'
        self.assertEqual(wisp.auth_headers_of(world)["Authorization"], "local")

    def test_extra_headers_bad_json_fails(self):
        world = _World().world
        world.get("env")["WISP_LLM_HEADERS"] = '{"x": "secret-value"'
        with self.assertRaises(SystemExit) as caught:
            wisp.auth_headers_of(world)
        self.assertEqual(caught.exception.code, 1)
        self.assertNotIn("secret-value", world.get("stderr").getvalue())

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
        self.assertEqual(http.url, URL_OF["anthropic"])
        self.assertEqual(http.headers["Authorization"], "Bearer k")
        self.assertNotIn("x-api-key", http.headers)
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
        self.assertEqual(http.url, URL_OF["openai-responses"])
        self.assertEqual(http.headers["Authorization"], "Bearer k")
        self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "yo")

    def test_chat_route_unchanged(self):
        world, http, chunks = self._run("openai-chat", [
            "data: %s" % json.dumps({"choices": [{"delta": {
                "content": "x"}, "finish_reason": None}]}),
            "data: [DONE]",
        ])
        self.assertEqual(http.url, URL_OF["openai-chat"])
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


class TestRequestUrl(unittest.TestCase):
    def test_full_url_lands_verbatim(self):
        world = _World().world
        url = ("https://res.openai.azure.com/openai/deployments/d/"
               "chat/completions?api-version=2024-10-21")
        world.get("env")["WISP_LLM_URL"] = url
        self.assertEqual(wisp.request_url_of(world), url)

    def test_bare_origin_fails(self):
        world = _World().world
        world.get("env")["WISP_LLM_URL"] = "https://example.test"
        with self.assertRaises(SystemExit) as caught:
            wisp.request_url_of(world)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("has no path", world.get("stderr").getvalue())

    def test_bad_scheme_fails(self):
        world = _World().world
        world.get("env")["WISP_LLM_URL"] = "example.test/v1/chat/completions"
        with self.assertRaises(SystemExit):
            wisp.request_url_of(world)
        self.assertIn("http or https", world.get("stderr").getvalue())

    def test_chat_body_names_the_session_for_the_cache(self):
        body = wisp.build_request(_World().world, RECORDS)
        self.assertEqual(body["prompt_cache_key"], "tmp")


class TestRedaction(unittest.TestCase):
    def test_query_secret_value_hidden(self):
        self.assertEqual(
            wisp.redact_query_of("https://h/p?api-version=1&api-key=abc&x=1"),
            "https://h/p?api-version=1&api-key=<redacted>&x=1")

    def test_every_secret_word_counts(self):
        text = "https://h/p?access_token=a&client_secret=b&model=ok"
        self.assertEqual(wisp.redact_query_of(text),
                         "https://h/p?access_token=<redacted>"
                         "&client_secret=<redacted>&model=ok")

    def test_plain_text_untouched(self):
        self.assertEqual(wisp.redact_query_of("no ?query=here"),
                         "no ?query=here")


class _LogSession:
    def __init__(self):
        self.lines = []

    def log(self, event, *fields):
        self.lines.append((event, fields))


class TestSafeLog(unittest.TestCase):
    def test_query_secret_never_reaches_the_log(self):
        world = wisp.World({})
        session = _LogSession()
        world.set("session", session)
        wisp.safe_log(world, "http", "url=https://h/p?api-key=abc&x=1")
        self.assertEqual(session.lines,
                         [("http", ("url=https://h/p?api-key=<redacted>&x=1",))])

    def test_plain_field_unchanged(self):
        world = wisp.World({})
        session = _LogSession()
        world.set("session", session)
        wisp.safe_log(world, "http", "url=https://h/p?x=1")
        self.assertEqual(session.lines, [("http", ("url=https://h/p?x=1",))])


class TestModelInfoFile(unittest.TestCase):
    def _world(self, temp):
        world = wisp.World({})
        world.set("fs", wisp.Fs(world))
        world.set("clock", _Clock())
        world.set("stderr", io.StringIO())
        world.set("session", wisp.Session(world))
        world.set("sessiondir", temp)
        world.set("env", {})
        return world

    def _write(self, path, data):
        with open(path, "w") as handle:
            json.dump(data, handle)

    def _modelcfg(self, temp):
        path = os.path.join(temp, "wisp.modelcfg")
        with open(path) as handle:
            return json.loads(handle.read())

    def test_copies_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            src = os.path.join(temp, "models.json")
            self._write(src, {"m": {"context": 1000, "input": 1}})
            world = self._world(temp)
            world.get("env")["WISP_LLM_MODEL_INFO_FILE"] = src
            world.get("session").refresh_model_cfg()
            self.assertEqual(self._modelcfg(temp),
                             {"m": {"context": 1000, "input": 1}})
            self.assertEqual(world.get("stderr").getvalue(), "")

    def test_unset_writes_nothing_and_warns_not(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp)
            world.get("session").refresh_model_cfg()
            self.assertFalse(
                os.path.exists(os.path.join(temp, "wisp.modelcfg")))
            self.assertEqual(world.get("stderr").getvalue(), "")

    def test_broken_file_keeps_the_hand_written_table(self):
        with tempfile.TemporaryDirectory() as temp:
            self._write(os.path.join(temp, "wisp.modelcfg"),
                        {"m": {"context": 5}})
            src = os.path.join(temp, "models.json")
            with open(src, "w") as handle:
                handle.write("not json")
            world = self._world(temp)
            world.get("env")["WISP_LLM_MODEL_INFO_FILE"] = src
            world.get("session").refresh_model_cfg()
            self.assertIn("warning:", world.get("stderr").getvalue())
            self.assertEqual(self._modelcfg(temp), {"m": {"context": 5}})

    def test_non_numeric_entry_warns_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            src = os.path.join(temp, "models.json")
            self._write(src, {"m": {"context": "big"}})
            world = self._world(temp)
            world.get("env")["WISP_LLM_MODEL_INFO_FILE"] = src
            world.get("session").refresh_model_cfg()
            self.assertIn("not a JSON object of model entries",
                          world.get("stderr").getvalue())
            self.assertFalse(
                os.path.exists(os.path.join(temp, "wisp.modelcfg")))


if __name__ == "__main__":
    unittest.main()
