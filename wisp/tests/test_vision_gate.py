"""Unit tests for vision handling: the WISP_LLM_VISION env, the
modelcfg vision field, the load_image always-stores rule, the
wire-time placeholder in all three builders, the --attach start
refusal, and the model-table shape check."""

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


def _red_png() -> bytes:
    """8x8 solid red PNG, stdlib only."""
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 8 for _ in range(8))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class _Stdin:
    def __init__(self, text=""):
        self._text = text

    def read_text(self):
        return self._text

    def lines(self):
        return iter(self._text.splitlines())

    def is_interactive(self):
        return False


class _Harness:
    """One session dir plus a world wired for run and tools."""

    def __init__(self, temp, env=None):
        self.sessiondir = os.path.join(temp, "run")
        os.makedirs(self.sessiondir)
        with open(os.path.join(self.sessiondir, "wisp.run.json"), "w") as h:
            json.dump({"model": "m", "thinking": None}, h)
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            h.write("")
        with open(os.path.join(self.sessiondir, "wisp.usage"), "w") as h:
            h.write("")
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("rng", wisp.Rng(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("model", "m")
        self.world.set("thinking", None)
        self.world.set("env", dict({
            "WISP_LLM_URL": "http://u/v1/chat/completions",
            "WISP_LLM_API_KEY": "k"}, **(env or {})))

    def modelcfg(self, entry):
        with open(os.path.join(self.sessiondir, "wisp.modelcfg"), "w") as h:
            json.dump({"m": entry}, h)

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def stderr(self):
        return self.world.get("stderr").getvalue()


class VisionEnabledTest(unittest.TestCase):
    def _vision(self, temp, env=None, entry=None):
        harness = _Harness(temp, env)
        if entry is not None:
            harness.modelcfg(entry)
        return wisp.vision_enabled_of(harness.world), harness

    def test_default_on_with_no_env_and_no_modelcfg(self):
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp)
            self.assertTrue(got)

    def test_env_off_words(self):
        for word in ("false", "0", "no", "off", " OFF "):
            with tempfile.TemporaryDirectory() as temp:
                got, _ = self._vision(temp, {"WISP_LLM_VISION": word})
                self.assertFalse(got, word)

    def test_env_on_words(self):
        for word in ("true", "1", "yes", "on"):
            with tempfile.TemporaryDirectory() as temp:
                got, _ = self._vision(temp, {"WISP_LLM_VISION": word})
                self.assertTrue(got, word)

    def test_unknown_env_value_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SystemExit):
                self._vision(temp, {"WISP_LLM_VISION": "maybe"})

    def test_modelcfg_vision_false_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp, entry={"vision": False})
            self.assertFalse(got)

    def test_modelcfg_vision_true_and_missing_key_stay_on(self):
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp, entry={"vision": True})
            self.assertTrue(got)
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp, entry={"context": 1000})
            self.assertTrue(got)

    def test_env_wins_over_modelcfg(self):
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp, {"WISP_LLM_VISION": "on"},
                                  {"vision": False})
            self.assertTrue(got)
        with tempfile.TemporaryDirectory() as temp:
            got, _ = self._vision(temp, {"WISP_LLM_VISION": "off"},
                                  {"vision": True})
            self.assertFalse(got)


class ModelTableVisionTest(unittest.TestCase):
    def test_bool_vision_passes(self):
        self.assertTrue(wisp.model_table_ok_of(
            {"m": {"context": 10, "vision": True}}))
        self.assertTrue(wisp.model_table_ok_of(
            {"m": {"context": 10, "vision": False}}))

    def test_non_bool_vision_is_rejected(self):
        self.assertFalse(wisp.model_table_ok_of(
            {"m": {"vision": "false"}}))
        self.assertFalse(wisp.model_table_ok_of(
            {"m": {"vision": 1}}))
        self.assertTrue(wisp.model_table_ok_of(
            {"m": {"vision": None}}))


class LoadImageStoreTest(unittest.TestCase):
    """load_image stores the image whatever the vision setting says:
    the request builder decides what reaches the wire, so a later run
    with vision on replays the bytes with no repair step."""

    def _run(self, world, arguments):
        tools = wisp.Tools(world)
        return tools.execute([{"id": "c1", "name": "load_image",
                               "arguments": json.dumps(arguments)}])[0]

    def _world(self, temp, env=None, entry=None):
        harness = _Harness(temp, env)
        if entry is not None:
            harness.modelcfg(entry)
        return harness.world

    def _image_path(self, temp):
        path = os.path.join(temp, "red.png")
        with open(path, "wb") as fh:
            fh.write(_red_png())
        return path

    def test_env_off_still_stores_the_image(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, {"WISP_LLM_VISION": "off"})
            record = self._run(world, {"path": self._image_path(temp)})
        self.assertEqual(record["exit"], 0)
        self.assertEqual(len(record["attachments"]), 1)
        self.assertIn("Loaded image: red.png", record["content"])

    def test_modelcfg_vision_false_still_stores_the_image(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, entry={"context": 1000,
                                             "vision": False})
            record = self._run(world, {"path": self._image_path(temp)})
        self.assertEqual(record["exit"], 0)
        self.assertEqual(len(record["attachments"]), 1)

    def test_default_keeps_loading_images(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp)
            record = self._run(world, {"path": self._image_path(temp)})
        self.assertEqual(record["exit"], 0)
        self.assertEqual(len(record["attachments"]), 1)


ATTACHMENT = {"name": "red.png", "media_type": "image/png",
              "data": "QUJD"}


def _tool_record():
    return {"type": "tool", "call_id": "c1", "name": "load_image",
            "content": "Loaded image: red.png (image/png, 71 bytes).",
            "exit": 0, "ms": 3, "attachments": [dict(ATTACHMENT)]}


def _user_record():
    return {"type": "user", "content": "look at this",
            "attachments": [dict(ATTACHMENT)]}


def _parts_text(parts):
    return [part.get("text") for part in parts if "text" in part]


def _image_part_types(parts):
    return [part["type"] for part in parts
            if part.get("type") in wisp.IMAGE_PART_TYPES]


class WirePlaceholderTest(unittest.TestCase):
    """Vision off replaces every image part at the request builder and
    leaves the stored record untouched."""

    def _world(self, temp, env=None, entry=None):
        harness = _Harness(temp, env)
        if entry is not None:
            harness.modelcfg(entry)
        return harness.world

    def test_chat_tool_image_becomes_tool_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, {"WISP_LLM_VISION": "off"})
            body = wisp.body_of_chat(world, [_tool_record()])
        parts = body["messages"][1]["content"]
        self.assertEqual(_image_part_types(parts), [])
        self.assertIn(wisp.TOOL_IMAGE_OMITTED_TEXT, _parts_text(parts))

    def test_chat_tool_image_still_sent_with_vision_on(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp)
            body = wisp.body_of_chat(world, [_tool_record()])
        parts = body["messages"][1]["content"]
        self.assertEqual(_image_part_types(parts), ["image_url"])
        self.assertIn("data:image/png;base64,QUJD",
                      json.dumps(parts))

    def test_chat_user_image_becomes_user_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, entry={"context": 1000,
                                             "vision": False})
            body = wisp.body_of_chat(world, [_user_record()])
        parts = body["messages"][0]["content"]
        self.assertEqual(_image_part_types(parts), [])
        self.assertIn(wisp.IMAGE_OMITTED_TEXT, _parts_text(parts))

    def test_responses_user_and_tool_images(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, {"WISP_LLM_VISION": "off"})
            user = wisp.items_of_responses(_user_record(), False)[0]
            tool = wisp.items_of_responses(_tool_record(), False)[0]
        self.assertEqual(_image_part_types(user["content"]), [])
        self.assertIn(wisp.IMAGE_OMITTED_TEXT,
                      _parts_text(user["content"]))
        self.assertEqual(_image_part_types(tool["output"]), [])
        self.assertIn(wisp.TOOL_IMAGE_OMITTED_TEXT,
                      _parts_text(tool["output"]))
        self.assertNotIn("input_image", json.dumps(tool))

    def test_anthropic_user_and_tool_images(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, {"WISP_LLM_VISION": "off"})
            user = wisp.items_of_anthropic(_user_record(), False)[0]
            tool = wisp.items_of_anthropic(_tool_record(), False)[0]
        tool_parts = tool["content"][0]["content"]
        self.assertEqual(_image_part_types(user["content"]), [])
        self.assertIn(wisp.IMAGE_OMITTED_TEXT,
                      _parts_text(user["content"]))
        self.assertEqual(_image_part_types(tool_parts), [])
        self.assertIn(wisp.TOOL_IMAGE_OMITTED_TEXT,
                      _parts_text(tool_parts))

    def test_vision_on_keeps_anthropic_image_parts(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp)
            user = wisp.items_of_anthropic(_user_record(), True)[0]
        self.assertEqual(_image_part_types(user["content"]), ["image"])

    def test_build_request_uses_the_modelcfg_vision_field(self):
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, entry={"context": 1000,
                                             "vision": False})
            body = wisp.build_request(world, [_user_record()])
        self.assertNotIn("image_url", json.dumps(body))
        self.assertIn(wisp.IMAGE_OMITTED_TEXT, json.dumps(body))

    def test_stored_record_keeps_its_bytes(self):
        record = _tool_record()
        with tempfile.TemporaryDirectory() as temp:
            world = self._world(temp, {"WISP_LLM_VISION": "off"})
            wisp.body_of_chat(world, [record])
            wisp.body_of_responses(world, [record])
            wisp.body_of_anthropic(world, [record])
        self.assertEqual(record["attachments"][0]["data"], "QUJD")


class _Opts:
    def __init__(self, sessiondir, attach=None):
        self.sessiondir = sessiondir
        self.context_guard = None
        self.attach = attach


class _Llm:
    def __init__(self, turns):
        self.turns = list(turns)

    def turn(self, records):
        return self.turns.pop(0)


def _stop_turn():
    return {"finish_reason": "stop",
            "assistant": {"type": "assistant",
                          "output": [{"type": "text", "text": "done"}]},
            "cached_tokens": 0}


class _Tools:
    def execute(self, calls):
        return []


class AttachGateTest(unittest.TestCase):
    def _png(self, temp):
        path = os.path.join(temp, "red.png")
        with open(path, "wb") as fh:
            fh.write(_red_png())
        return path

    def test_attach_refused_under_vision_off(self):
        with tempfile.TemporaryDirectory() as temp:
            harness = _Harness(temp, {"WISP_LLM_VISION": "off"})
            harness.world.set("stdin", _Stdin("look at this"))
            harness.world.set("llm", _Llm([]))
            opts = _Opts(harness.sessiondir, attach=[self._png(temp)])
            with self.assertRaises(SystemExit):
                wisp.run_agent_loop(harness.world, opts)
            self.assertIn("wisp run: --attach:", harness.stderr())
            self.assertIn("no image content", harness.stderr())
            self.assertEqual(harness.jsonl(), [])

    def test_attach_refused_under_modelcfg_vision_false(self):
        with tempfile.TemporaryDirectory() as temp:
            harness = _Harness(temp)
            harness.modelcfg({"context": 1000, "vision": False})
            harness.world.set("stdin", _Stdin("look at this"))
            harness.world.set("llm", _Llm([]))
            opts = _Opts(harness.sessiondir, attach=[self._png(temp)])
            with self.assertRaises(SystemExit):
                wisp.run_agent_loop(harness.world, opts)
            self.assertIn("wisp run: --attach:", harness.stderr())

    def test_no_attach_runs_on_under_vision_off(self):
        with tempfile.TemporaryDirectory() as temp:
            harness = _Harness(temp, {"WISP_LLM_VISION": "off"})
            harness.world.set("stdin", _Stdin("plain text work"))
            harness.world.set("llm", _Llm([_stop_turn()]))
            harness.world.set("tools", _Tools())
            rc = wisp.run_agent_loop(harness.world,
                                     _Opts(harness.sessiondir))
            self.assertEqual(rc, 0)
            self.assertEqual(len(harness.jsonl()), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
