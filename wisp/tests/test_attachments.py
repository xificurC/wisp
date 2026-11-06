"""Unit tests for image attachments: sniff, fail-fast intake, wire
parts on all three providers, chat byte-identity for text-only
records, surgery that spares image parts, and the render-past
marker."""

import base64
import io
import json
import os
import struct
import tempfile
import unittest
import zlib


def _load_wisp():
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


def _red_png() -> bytes:
    """8x8 solid red PNG, stdlib only."""
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 8 for _ in range(8))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _wide_png(width: int) -> bytes:
    """One-row solid red PNG of the given width, stdlib only."""
    raw = b"\x00" + b"\xff\x00\x00" * width
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", width, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


ATT = {"name": "red.png", "media_type": "image/png",
       "data": base64.b64encode(_red_png()).decode("ascii")}
URI = "data:image/png;base64," + ATT["data"]

TEXT_RECORDS = [
    _rec("system", content="be terse"),
    _rec("user", content="hello"),
    _rec("assistant", output=[
        {"type": "text", "text": "hi"},
        {"type": "tool_call", "id": "c1", "name": "bash",
         "arguments": "{\"command\":\"echo x\"}"},
    ], finish_reason="tool_calls", usage=[]),
    _rec("tool", call_id="c1", name="bash", content="x", exit=0),
    _rec("user", content="and now?"),
    _rec("assistant", output=[{"type": "text", "text": "done"}],
         finish_reason="stop", usage=[]),
]


class _World:
    """A world with just what build_request and load_attachments read."""

    def __init__(self, api=None, thinking=None):
        self.world = wisp.World({})
        env = {"WISP_LLM_URL": "https://example.test/v1/chat/completions",
               "WISP_LLM_API_KEY": "k"}
        if api:
            env["WISP_LLM_API"] = api
        self.world.set("env", env)
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("sessiondir", "/tmp")
        self.world.set("model", "m")
        self.world.set("thinking", thinking)


def _user_parts(body, api):
    """Dig the first user content parts array out of a provider body."""
    if api == "anthropic":
        msgs = body["messages"]
        for m in msgs:
            if m["role"] == "user" and m["content"][0]["type"] == "text":
                return m["content"]
    elif api == "openai-responses":
        for item in body["input"]:
            if item.get("role") == "user":
                return item["content"]
    else:
        for m in body["messages"]:
            if m.get("role") == "user" and isinstance(m["content"], list):
                return m["content"]
    raise AssertionError("no user parts found")


class TestSniff(unittest.TestCase):
    def test_png(self):
        self.assertEqual(wisp.sniff_image_media(b"\x89PNG\r\n\x1a\n...."),
                         "image/png")

    def test_jpeg(self):
        self.assertEqual(wisp.sniff_image_media(b"\xff\xd8\xff\xe0"),
                         "image/jpeg")

    def test_gif87a(self):
        self.assertEqual(wisp.sniff_image_media(b"GIF87a"), "image/gif")

    def test_gif89a(self):
        self.assertEqual(wisp.sniff_image_media(b"GIF89a"), "image/gif")

    def test_webp(self):
        self.assertEqual(
            wisp.sniff_image_media(b"RIFF\x00\x00\x00\x00WEBPVP8 "),
            "image/webp")

    def test_text_is_none(self):
        self.assertIsNone(wisp.sniff_image_media(b"hello world"))

    def test_empty_is_none(self):
        self.assertIsNone(wisp.sniff_image_media(b""))


class TestLoadAttachments(unittest.TestCase):
    def _world(self):
        return _World().world

    def test_png_stores(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "red.png")
            with open(path, "wb") as fh:
                fh.write(_red_png())
            out = wisp.load_attachments(self._world(), [path])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "red.png")
        self.assertEqual(out[0]["media_type"], "image/png")
        self.assertEqual(base64.b64decode(out[0]["data"]), _red_png())

    def test_missing_file_fails_fast(self):
        with self.assertRaises(SystemExit):
            wisp.load_attachments(self._world(), ["/no/such/file.png"])

    def test_non_image_fails_fast(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "not.png")
            with open(path, "wb") as fh:
                fh.write(b"plain text, no magic")
            with self.assertRaises(SystemExit):
                wisp.load_attachments(self._world(), [path])

    def test_empty_paths_empty_list(self):
        self.assertEqual(wisp.load_attachments(self._world(), []), [])


class TestWireParts(unittest.TestCase):
    def _att_record(self, **user_kw):
        rec = _rec("user", content="look", attachments=[ATT])
        rec.update(user_kw)
        return [_rec("system", content="s"), rec]

    def test_all_three_providers_from_one_record(self):
        for api in ("openai-chat", "openai-responses", "anthropic"):
            body = wisp.build_request(_World(api=api).world,
                                      self._att_record())
            parts = _user_parts(body, api)
            self.assertEqual(parts[0]["type"],
                             {"openai-chat": "text",
                              "openai-responses": "input_text",
                              "anthropic": "text"}[api], api)
            self.assertEqual(parts[0][
                {"openai-chat": "text",
                 "openai-responses": "text",
                 "anthropic": "text"}[api]], "look", api)
            img = parts[1]
            if api == "openai-chat":
                self.assertEqual(img["type"], "image_url")
                self.assertEqual(img["image_url"]["url"], URI)
            elif api == "openai-responses":
                self.assertEqual(img["type"], "input_image")
                self.assertEqual(img["image_url"], URI)
            else:
                self.assertEqual(img["type"], "image")
                self.assertEqual(img["source"],
                                 {"type": "base64",
                                  "media_type": "image/png",
                                  "data": ATT["data"]})

    def test_two_attachments_keep_order(self):
        att2 = dict(ATT, name="b.jpg", media_type="image/jpeg",
                    data="eHg=")
        recs = [_rec("user", content="two",
                     attachments=[ATT, att2])]
        body = wisp.build_request(_World("openai-chat").world, recs)
        parts = _user_parts(body, "openai-chat")
        self.assertEqual([p["type"] for p in parts],
                         ["text", "image_url", "image_url"])
        self.assertEqual(parts[1]["image_url"]["url"], URI)
        self.assertEqual(parts[2]["image_url"]["url"],
                         "data:image/jpeg;base64,eHg=")

    def test_text_only_records_stay_strings(self):
        for api in ("openai-chat", "openai-responses", "anthropic"):
            body = wisp.build_request(_World(api=api).world, TEXT_RECORDS)
            if api == "openai-chat":
                for m in body["messages"]:
                    if m.get("role") == "user":
                        self.assertIsInstance(m["content"], str)


class TestChatGoldenBody(unittest.TestCase):
    """The chat body for text-only records, byte-pinned: a change must
    never alter one byte for existing sessions. The literal is the true
    current output, generated once and pinned."""

    GOLDEN = '{"model": "m", "messages": [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "bash", "arguments": "{\\"command\\":\\"echo x\\"}"}}]}, {"role": "tool", "tool_call_id": "c1", "content": "x"}, {"role": "user", "content": "and now?"}, {"role": "assistant", "content": "done"}], "tools": [{"type": "function", "function": {"name": "bash", "description": "Run a bash command and return its output.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The bash command to run."}, "maxKilobytes": {"type": "number", "description": "Maximum output size in kilobytes. Default 5."}, "timeoutSeconds": {"type": "number", "description": "Command timeout in seconds. Default 5."}}, "required": ["command"]}}}, {"type": "function", "function": {"name": "python3", "description": "Run a python3 command and return its output.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The python3 command to run. It is Python code, not a shell string."}, "maxKilobytes": {"type": "number", "description": "Maximum output size in kilobytes. Default 5."}, "timeoutSeconds": {"type": "number", "description": "Command timeout in seconds. Default 5."}}, "required": ["command"]}}}, {"type": "function", "function": {"name": "load_image", "description": "Load an image file into the conversation so you can see it. Supports PNG, JPEG, GIF, and WebP. The image is resized to the default limits unless resize is false.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to the image file."}, "resize": {"type": "boolean", "description": "Resize the image to the default dimension and byte limits. Default true. Set false to send the file bytes unchanged."}}, "required": ["path"]}}}], "stream": true, "stream_options": {"include_usage": true}, "prompt_cache_key": "tmp"}'

    def test_golden(self):
        body = wisp.build_request(_World(thinking=None).world,
                                  TEXT_RECORDS)
        self.assertEqual(json.dumps(body), self.GOLDEN)


class TestSurgerySparesImages(unittest.TestCase):
    def test_steer_tag_stays_in_text_part(self):
        for api in ("openai-chat", "openai-responses", "anthropic"):
            rec = _rec("user", content="look", attachments=[ATT],
                       wisp_steered=True)
            body = wisp.build_request(
                _World(api=api).world,
                [_rec("system", content="s"), rec])
            parts = _user_parts(body, api)
            text = parts[0][
                {"openai-chat": "text", "openai-responses": "text",
                 "anthropic": "text"}[api]]
            self.assertIn(wisp.STEER_TAG, text, api)
            self.assertEqual(len(parts), 2, api)
            img = parts[1]
            blob = json.dumps(img)
            self.assertNotIn(wisp.STEER_TAG, blob, api)


class TestRenderMarker(unittest.TestCase):
    def test_prompt_carries_marker_lines(self):
        recs = [_rec("user", content="look", attachments=[ATT])]
        lines = list(wisp.records_to_stream(recs))
        payload = json.loads(lines[0][len("data: "):])
        self.assertEqual(
            payload["content"],
            "look\n[attachment: red.png, image/png]")

    def test_plain_prompt_unchanged(self):
        recs = [_rec("user", content="look")]
        lines = list(wisp.records_to_stream(recs))
        payload = json.loads(lines[0][len("data: "):])
        self.assertEqual(payload["content"], "look")


TOOL_RECORDS = [
    _rec("system", content="s"),
    _rec("user", content="look at this"),
    _rec("assistant", output=[
        {"type": "tool_call", "id": "c1", "name": "load_image",
         "arguments": "{\"path\":\"red.png\"}"},
    ], finish_reason="tool_calls", usage=[]),
    _rec("tool", call_id="c1", name="load_image",
         content="Loaded image: red.png (image/png, 8 bytes).",
         exit=0, attachments=[ATT]),
]


class TestToolRecordWire(unittest.TestCase):
    def _body(self, api):
        return wisp.build_request(_World(api=api).world, TOOL_RECORDS)

    def test_anthropic_tool_result_carries_image(self):
        body = self._body("anthropic")
        message = body["messages"][-1]
        self.assertEqual(message["role"], "user")
        block = message["content"][0]
        self.assertEqual(block["type"], "tool_result")
        self.assertEqual(block["tool_use_id"], "c1")
        self.assertEqual(block["content"][0]["type"], "text")
        self.assertEqual(block["content"][1]["type"], "image")
        self.assertEqual(block["content"][1]["source"],
                         {"type": "base64", "media_type": "image/png",
                          "data": ATT["data"]})

    def test_responses_output_carries_image(self):
        body = self._body("openai-responses")
        item = [i for i in body["input"]
                if i.get("type") == "function_call_output"][0]
        self.assertEqual(item["output"][0]["type"], "input_text")
        self.assertEqual(item["output"][1]["type"], "input_image")
        self.assertEqual(item["output"][1]["image_url"], URI)

    def test_chat_adds_one_user_message_after_tool(self):
        body = self._body("openai-chat")
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "tool", "user"])
        tool = body["messages"][3]
        self.assertIsInstance(tool["content"], str)
        user = body["messages"][4]
        self.assertEqual(user["content"][0]["type"], "text")
        self.assertEqual(user["content"][1]["type"], "image_url")
        self.assertEqual(user["content"][1]["image_url"]["url"], URI)

    def test_chat_text_only_tool_still_a_string(self):
        recs = [r for r in TOOL_RECORDS if r["type"] != "tool"] + [
            _rec("tool", call_id="c1", name="load_image",
                 content="Loaded image.", exit=0)]
        body = wisp.build_request(_World("openai-chat").world, recs)
        self.assertEqual([m["role"] for m in body["messages"]],
                         ["system", "user", "assistant", "tool"])

    def test_replay_shows_attachment(self):
        payloads = [json.loads(line[len("data: "):])
                    for line in wisp.records_to_stream(TOOL_RECORDS)]
        result = [p for p in payloads if p.get("wisp") == "tool_result"][0]
        self.assertEqual(result["attachments"],
                         [{"name": "red.png", "media_type": "image/png"}])


class TestLoadImageTool(unittest.TestCase):
    def _world(self, td):
        world = wisp.World({})
        world.set("env", {})
        world.set("stderr", io.StringIO())
        world.set("stdout", io.StringIO())
        world.set("fs", wisp.Fs(world))
        world.set("sessiondir", td)
        world.set("clock", wisp.Clock(world))
        world.set("rng", wisp.Rng(world))
        return world

    def _run(self, world, arguments):
        tools = wisp.Tools(world)
        return tools.execute([{"id": "c1", "name": "load_image",
                               "arguments": json.dumps(arguments)}])[0]

    def test_resize_false_keeps_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "wide.png")
            raw = _wide_png(2001)
            with open(path, "wb") as fh:
                fh.write(raw)
            record = self._run(self._world(td), {"path": path, "resize": False})
        self.assertEqual(record["exit"], 0)
        self.assertEqual(len(record["attachments"]), 1)
        self.assertEqual(base64.b64decode(record["attachments"][0]["data"]), raw)
        self.assertEqual(record["attachments"][0]["media_type"], "image/png")

    @unittest.skipUnless(wisp._pillow() is not None, "Pillow is not installed")
    def test_resize_true_fits_default_dimension(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "wide.png")
            raw = _wide_png(2001)
            with open(path, "wb") as fh:
                fh.write(raw)
            record = self._run(self._world(td), {"path": path})
        self.assertEqual(record["exit"], 0)
        self.assertIn("original 2001x1", record["content"])
        self.assertIn("displayed at 2000x1", record["content"])
        self.assertEqual(record["attachments"][0]["media_type"], "image/png")

    def test_small_image_with_resize_true_keeps_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "red.png")
            with open(path, "wb") as fh:
                fh.write(_red_png())
            record = self._run(self._world(td), {"path": path})
        self.assertEqual(record["exit"], 0)
        self.assertEqual(base64.b64decode(record["attachments"][0]["data"]),
                         _red_png())
        self.assertFalse(record["content"].startswith("[Image:"))

    def test_missing_file_degrades_to_text(self):
        with tempfile.TemporaryDirectory() as td:
            record = self._run(self._world(td), {"path": "/no/such.png"})
        self.assertEqual(record["exit"], 1)
        self.assertNotIn("attachments", record)
        self.assertIn("no such file", record["content"])

    def test_non_image_degrades_to_text(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "notes.txt")
            with open(path, "wb") as fh:
                fh.write(b"plain text")
            record = self._run(self._world(td), {"path": path})
        self.assertEqual(record["exit"], 1)
        self.assertNotIn("attachments", record)
        self.assertIn("not a supported image", record["content"])


if __name__ == "__main__":
    unittest.main()
