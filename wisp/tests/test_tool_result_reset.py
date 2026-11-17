"""Unit tests for the tool result block: content first, status last, SGR
reset after both.

A tool result may end with an active color or other SGR state: the
command never reset it, or the output cap cut the command's own reset
off. The renderer must close that state after the block so it cannot
bleed into later render output. ESC[0m with no active attributes is a
no-op, so the reset is unconditional. The status line trails the
content because a live result streams its output as it runs; the
model-facing text keeps the status first. The extensionless wisp
module imports by path, so the package stays stdlib only."""
import importlib.machinery
import importlib.util
import io
import json
import os
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

RESET = "\x1b[0m"


def _renderer():
    world = wisp.World({})
    world.set("stdout", io.StringIO())
    world.set("env", {})
    return world, wisp.Renderer(world)


def _render(payload):
    world, renderer = _renderer()
    renderer.render_line("data: " + json.dumps(payload))
    renderer.finish()
    return world.get("stdout").getvalue()


class ToolResultResetTest(unittest.TestCase):
    def test_reset_after_content_with_active_color(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 0,
                       "content": "\x1b[31mRED"})
        self.assertIn("\x1b[31mRED\nwisp:tool bash exit=0\n" + RESET + "\n",
                      out)

    def test_reset_after_content_with_trailing_newline(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 0,
                       "content": "\x1b[31mRED\n"})
        self.assertIn("\x1b[31mRED\nwisp:tool bash exit=0\n" + RESET + "\n",
                      out)

    def test_reset_after_failed_exit(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 124,
                       "content": "\x1b[33m"})
        self.assertIn("\x1b[33m\nwisp:tool bash exit=124\n" + RESET + "\n",
                      out)

    def test_reset_present_on_clean_content(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 0,
                       "content": "plain output"})
        self.assertIn("plain output\nwisp:tool bash exit=0\n" + RESET + "\n",
                      out)

    def test_status_line_lands_after_the_content(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 1,
                       "content": "the output\n", "ms": 7})
        self.assertTrue(out.startswith(
            "the output\nwisp:tool bash exit=1 ms=7\n"), out)

    def test_status_line_alone_on_empty_output(self):
        out = _render({"wisp": "tool_result", "name": "bash", "exit": 0,
                       "content": "", "ms": 4})
        self.assertEqual(out, "wisp:tool bash exit=0 ms=4 bytes=0\n"
                              + RESET + "\n")

    def test_streamed_output_does_not_print_twice(self):
        world, renderer = _renderer()
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_output", "call_id": "c1",
             "content_delta": "half "}))
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_output", "call_id": "c1",
             "content_delta": "done\n"}))
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_result", "name": "bash", "call_id": "c1",
             "exit": 0, "content": "half done\n", "ms": 9}))
        renderer.finish()
        out = world.get("stdout").getvalue()
        self.assertEqual(out.count("half done"), 1, out)
        self.assertTrue(out.endswith("wisp:tool bash exit=0 ms=9\n"
                                     + RESET + "\n"), out)

    def test_reset_before_the_next_rendered_message(self):
        world, renderer = _renderer()
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_result", "name": "bash", "exit": 0,
             "content": "\x1b[31mRED"}))
        renderer.render_line("data: " + json.dumps(
            {"choices": [{"delta": {"content": "done"}}]}))
        renderer.finish()
        out = world.get("stdout").getvalue()
        red = out.index("\x1b[31mRED")
        done = out.index("done")
        reset = out.index(RESET, red)
        self.assertLess(red, reset)
        self.assertLess(reset, done)


if __name__ == "__main__":
    unittest.main()
