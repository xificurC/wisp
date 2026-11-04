"""Unit tests for the SGR reset after tool result content.

A tool result may end with an active color or other SGR state: the
command never reset it, or the output cap cut the command's own
reset off. The renderer must close that state after the content so
it cannot bleed into later render output. ESC[0m with no active
attributes is a no-op, so the reset is unconditional. The
extensionless wisp module imports by path, so the package stays
stdlib only."""
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


def _render(payload):
    world = wisp.World({})
    world.set("stdout", io.StringIO())
    world.set("env", {})
    renderer = wisp.Renderer(world)
    renderer.render_line("data: " + json.dumps(payload))
    renderer.finish()
    return world.get("stdout").getvalue()


class ToolResultResetTest(unittest.TestCase):
    def test_reset_after_content_with_active_color(self):
        out = _render({"wisp": "tool_result", "exit": 0,
                       "content": "\x1b[31mRED"})
        self.assertIn("\x1b[31mRED\n" + RESET + "\n", out)

    def test_reset_after_content_with_trailing_newline(self):
        out = _render({"wisp": "tool_result", "exit": 0,
                       "content": "\x1b[31mRED\n"})
        self.assertIn("\x1b[31mRED\n" + RESET + "\n", out)

    def test_reset_after_failed_exit(self):
        out = _render({"wisp": "tool_result", "exit": 124,
                       "content": "\x1b[33m"})
        self.assertIn("\x1b[33m\n" + RESET + "\n", out)

    def test_reset_present_on_clean_content(self):
        out = _render({"wisp": "tool_result", "exit": 0,
                       "content": "plain output"})
        self.assertIn("plain output\n" + RESET + "\n", out)

    def test_reset_before_the_next_rendered_message(self):
        world = wisp.World({})
        world.set("stdout", io.StringIO())
        world.set("env", {})
        renderer = wisp.Renderer(world)
        renderer.render_line("data: " + json.dumps(
            {"wisp": "tool_result", "exit": 0,
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
