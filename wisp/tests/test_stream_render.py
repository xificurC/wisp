"""Unit tests for live streaming: tool-call fragments, the streamed
output head, and the renderer shape the two new markers produce.

The producer normalizes every provider dialect before it injects a
marker, so these tests feed normalized chunks to `tool_deltas_of` and
check one marker per dialect. The renderer tests pin the live shape: a
call opens a fence and the command grows; the result streams its head
and one `wisp:tool` status line closes the block with the call's
limits and the outcome.
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest


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


class Out:
    """A stdout that records every write."""

    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text

    def flush(self):
        pass


class Session:
    def __init__(self):
        self.lines = []

    def log(self, event, *fields):
        self.lines.append((event, fields))


class Exec:
    """A fake executor that replays chosen head bytes through on_head."""

    def __init__(self, head=b"", exit=0, spill=None):
        self.head = head
        self.exit = exit
        self.spill = spill
        self.seen = []

    def run(self, argv, seconds, cap_bytes, spill_path_of, on_head=None):
        self.seen.append((argv, seconds, cap_bytes))
        if on_head is not None:
            for start in range(0, len(self.head), 4):
                on_head(self.head[start:start + 4])
        return self.exit, self.head, self.spill, False


class Fs:
    def __init__(self):
        self.files = {}

    def size(self, path):
        return len(self.files.get(path, b""))

    def mkdir(self, path):
        pass

    def write_text(self, path, text):
        self.files[path] = text


def renderer_world():
    world = wisp.World({})
    world.set("env", {})
    out = Out()
    world.set("stdout", out)
    return world, out


def draw(lines):
    """Feed data: payloads to a fresh renderer and return its text."""
    world, out = renderer_world()
    renderer = wisp.Renderer(world)
    for payload in lines:
        renderer.render_line("data: " + json.dumps(payload))
    renderer.finish()
    return out.text


class ToolDeltasTest(unittest.TestCase):
    def test_openai_chat_name_fragment(self):
        chunk = {"choices": [{"delta": {"tool_calls": [{
            "index": 0, "id": "c1", "type": "function",
            "function": {"name": "bash", "arguments": ""}}]}}]}
        self.assertEqual(wisp.tool_deltas_of(chunk), [
            {"wisp": "tool_delta", "index": 0, "id": "c1", "name": "bash"}])

    def test_responses_argument_fragment(self):
        chunk = wisp.responses_chunk_of({
            "type": "response.function_call_arguments.delta",
            "output_index": 2, "delta": "{\"comm"})
        self.assertEqual(wisp.tool_deltas_of(chunk), [
            {"wisp": "tool_delta", "index": 2, "arguments_delta": "{\"comm"}])

    def test_anthropic_block_start(self):
        chunk = wisp.anthropic_chunk_of({
            "type": "content_block_start", "index": 1,
            "content_block": {"type": "tool_use", "id": "tu_1",
                              "name": "bash", "input": {}}})
        self.assertEqual(wisp.tool_deltas_of(chunk), [
            {"wisp": "tool_delta", "index": 1, "id": "tu_1",
             "name": "bash"}])

    def test_text_chunk_yields_no_marker(self):
        chunk = wisp.chat_chunk_of({"choices": [{"message": {"content": "hi"}}]})
        self.assertEqual(wisp.tool_deltas_of(chunk), [])


class SseStreamInjectionTest(unittest.TestCase):
    def test_tool_fragments_reach_stdout_as_markers(self):
        world = wisp.World({})
        out = Out()
        world.set("env", {"WISP_LLM_URL": "https://x.test/v1/chat/completions",
                          "WISP_LLM_API_KEY": "k"})
        world.set("stdout", out)
        world.set("stderr", Out())
        world.set("clock", wisp.Clock(world))
        world.set("sessiondir", "/tmp")
        world.set("session", Session())
        world.set("fs", Fs())
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"tool_calls": [{
                "index": 0, "id": "c1", "type": "function",
                "function": {"name": "bash", "arguments": ""}}]}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"tool_calls": [{
                "index": 0, "function": {"arguments": "{\"command\":"}}]}}]}),
        ]

        class Http:
            def post_stream(self, url, headers, body, meta=None):
                for line in lines:
                    yield line

        world.set("http", Http())
        chunks = list(wisp.sse_stream(world, {"model": "m"}))
        self.assertEqual(len(chunks), 2)
        markers = [json.loads(line[len("data: "):])
                   for line in out.text.splitlines()
                   if line.startswith("data: ")]
        deltas = [m for m in markers if m.get("wisp") == "tool_delta"]
        self.assertEqual(deltas, [
            {"wisp": "tool_delta", "index": 0, "id": "c1", "name": "bash"},
            {"wisp": "tool_delta", "index": 0, "arguments_delta": "{\"command\":"}])


class CallStreamTest(unittest.TestCase):
    def test_command_grows_and_one_status_line_closes_the_call(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0, "id": "c1", "name": "bash"},
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"command\": \"echo \\"},
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "\"hi\\\" there\"}"},
            {"wisp": "tool_call", "name": "bash", "timeoutSeconds": 30,
             "maxKilobytes": 50, "command": "echo \"hi\" there"},
            {"wisp": "tool_output", "call_id": "c1",
             "content_delta": "hi there\n"},
            {"wisp": "tool_result", "name": "bash", "call_id": "c1",
             "content": "hi there\n", "exit": 0, "ms": 5},
        ])
        self.assertEqual(
            out,
            '```bash\necho "hi" there\n```\n\n'
            'hi there\n'
            'wisp:tool bash timeoutSeconds=30 maxKilobytes=50'
            ' exit=0 ms=5\n\x1b[0m\n', out)

    def test_a_split_escape_is_not_consumed(self):
        text, used, closed = wisp.decode_json_prefix('echo \\')
        self.assertEqual((text, used, closed), ("echo ", 5, False))
        text, used, closed = wisp.decode_json_prefix('\\"hi\\" there"')
        self.assertEqual((text, used, closed), ('"hi" there', 12, True))

    def test_a_surrogate_pair_split_across_fragments(self):
        text, used, closed = wisp.decode_json_prefix('\\ud83d')
        self.assertEqual((text, used, closed), ("", 0, False))
        text, used, closed = wisp.decode_json_prefix('\\ud83d\\ude00"')
        self.assertEqual((text, used, closed), ("\U0001F600", 12, True))

    def test_load_image_streams_its_path(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0, "name": "load_image"},
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"path\": \"/tmp/p"},
            {"wisp": "tool_delta", "index": 0, "arguments_delta": "x.png\"}"},
            {"wisp": "tool_call", "name": "load_image", "command": "/tmp/px.png",
             "timeoutSeconds": 5, "maxKilobytes": 5},
        ])
        self.assertEqual(
            out,
            '```\n/tmp/px.png\n```\n', out)

    def test_finish_closes_a_dangling_fence(self):
        world, out = renderer_world()
        renderer = wisp.Renderer(world)
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_delta", "index": 0, "name": "bash",
             "arguments_delta": "{\"command\": \"ls"}))
        renderer.finish()
        self.assertEqual(out.text, "```bash\nls\n```\n", out.text)

    def test_a_replayed_call_draws_the_whole_block(self):
        out = draw([{"wisp": "tool_call", "name": "bash",
                     "command": "echo hi",
                     "timeoutSeconds": 5, "maxKilobytes": 5}])
        self.assertEqual(out, "```bash\necho hi\n```\n", out)

    def test_the_python3_fence_names_python3(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0, "name": "python3"},
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"command\": \"print(1)\"}"},
        ])
        self.assertEqual(out, "```python3\nprint(1)\n```\n", out)

    def test_a_name_trailing_an_argument_fragment_still_tags_the_fence(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"command\": \"ls"},
            {"wisp": "tool_delta", "index": 0, "name": "bash"},
        ])
        self.assertEqual(out, "```bash\nls\n```\n", out)

    def test_a_call_that_never_learns_its_name_draws_no_fence(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"command\": \"ls"},
        ])
        self.assertEqual(out, "", out)

    def test_a_nameless_call_still_draws_from_the_inject(self):
        out = draw([
            {"wisp": "tool_delta", "index": 0,
             "arguments_delta": "{\"command\": \"ls"},
            {"wisp": "tool_call", "name": "bash", "command": "ls",
             "timeoutSeconds": 5, "maxKilobytes": 5},
        ])
        self.assertEqual(out, "```bash\nls\n```\n", out)


class OutputStreamTest(unittest.TestCase):
    def test_head_streams_and_the_status_closes_the_result(self):
        out = draw([
            {"wisp": "tool_output", "call_id": "c1", "content_delta": "half "},
            {"wisp": "tool_output", "call_id": "c1", "content_delta": "done\n"},
            {"wisp": "tool_result", "name": "bash", "call_id": "c1",
             "content": "half done\n", "exit": 0, "ms": 9},
        ])
        self.assertEqual(out.count("half done"), 1, out)
        self.assertTrue(out.endswith(
            "half done\nwisp:tool bash exit=0 ms=9\n\x1b[0m\n"), out)

    def test_a_fragment_without_a_newline_keeps_the_status_on_its_line(self):
        out = draw([
            {"wisp": "tool_output", "call_id": "c1", "content_delta": "tail"},
            {"wisp": "tool_result", "name": "bash", "call_id": "c1",
             "content": "tail", "exit": 0, "ms": 3},
        ])
        self.assertEqual(out, "tail\nwisp:tool bash exit=0 ms=3\n\x1b[0m\n", out)


class ExecutorHeadTest(unittest.TestCase):
    def test_the_cap_bounds_the_stream_and_the_spill_keeps_all(self):
        world = wisp.World({})
        world.set("clock", wisp.Clock(world))
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            spill = os.path.join(tmp, "spill")
            rc, head, path, abandoned = wisp.Executor(world).run(
                ["bash", "-c", "printf abcdefghij"], 5, 5,
                lambda: spill, seen.append)
            self.assertEqual(rc, 0)
            self.assertEqual(head, b"abcde")
            self.assertEqual(b"".join(seen), b"abcde")
            self.assertEqual(path, spill)
            with open(spill, "rb") as handle:
                self.assertEqual(handle.read(), b"abcdefghij")

    def test_a_fitting_head_creates_no_spill(self):
        world = wisp.World({})
        world.set("clock", wisp.Clock(world))
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            spill = os.path.join(tmp, "spill")
            rc, head, path, abandoned = wisp.Executor(world).run(
                ["bash", "-c", "printf abc"], 5, 5,
                lambda: spill, seen.append)
            self.assertEqual(head, b"abc")
            self.assertEqual(b"".join(seen), b"abc")
            self.assertIsNone(path)


class ToolOutputMarkerTest(unittest.TestCase):
    def test_the_head_streams_and_the_record_keeps_the_full_head(self):
        world, out = renderer_world()
        world.set("clock", wisp.Clock(world))
        world.set("fs", Fs())
        world.set("session", Session())
        world.set("sessiondir", "/sess")
        world.set("exec", Exec(b"hi\nthere\n"))
        record = wisp.Tools(world)._execute_one({
            "id": "c1", "name": "bash",
            "arguments": json.dumps({"command": "echo hi"})})
        self.assertEqual(record["content"], "hi\nthere\n")
        payloads = [json.loads(line[len("data: "):])
                    for line in out.text.splitlines()]
        kinds = [p.get("wisp") for p in payloads]
        self.assertEqual(kinds, ["tool_call", "tool_output", "tool_output",
                                 "tool_output", "tool_result"])
        streamed = "".join(p["content_delta"] for p in payloads
                           if p.get("wisp") == "tool_output")
        self.assertEqual(streamed, "hi\nthere\n")
        self.assertEqual(payloads[-1]["content"], "hi\nthere\n")
        text = draw(payloads)
        self.assertEqual(text.count("hi\nthere"), 1, text)
        self.assertIn("```bash\necho hi\n```\n\nhi\nthere\n", text)
        self.assertRegex(
            text,
            r"wisp:tool bash timeoutSeconds=5 maxKilobytes=5"
            r" exit=0 ms=\d+\n\x1b\[0m\n$")


if __name__ == "__main__":
    unittest.main()
