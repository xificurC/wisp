"""Unit tests for the discard rule in _reload_committed.

A trailing assistant record with tool-call blocks and no tool
results is a partial round: the reload drops it. Every drop writes
one dropped line to wisp.log, so a lost tail is never silent. The
extensionless wisp module imports by path, so the package stays
stdlib only."""
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


def _tool_call(cid="c1"):
    return {"type": "tool_call", "id": cid, "name": "bash",
            "arguments": "{\"command\":\"echo x\"}"}


def _tool(cid="c1"):
    return {"type": "tool", "call_id": cid, "name": "bash",
            "content": "x", "exit": 0}


def _assistant(*blocks, finish="tool_calls"):
    return {"type": "assistant", "output": list(blocks),
            "finish_reason": finish}


def _user(content):
    return {"type": "user", "content": content}


class _Harness:
    """One session dir with a jsonl file, wired for reloads."""

    def __init__(self):
        self._temp = tempfile.TemporaryDirectory()
        self.sessiondir = os.path.join(self._temp.name, "run")
        os.makedirs(self.sessiondir)
        self.path = os.path.join(self.sessiondir, "wisp.jsonl")
        with open(self.path, "w") as handle:
            handle.write("")
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "u",
                               "WISP_LLM_API_KEY": "k"})

    def write(self, records):
        with open(self.path, "w") as handle:
            handle.write("".join(json.dumps(rec, ensure_ascii=False)
                                 + "\n" for rec in records))

    def write_text(self, text):
        with open(self.path, "w") as handle:
            handle.write(text)

    def reload(self):
        return wisp.Session(self.world)._reload_committed(self.path)

    def log_lines(self, tag):
        path = os.path.join(self.sessiondir, "wisp.log")
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return [ln for ln in handle.read().splitlines()
                    if " %s " % tag in ln]

    def jsonl(self):
        with open(self.path) as handle:
            return [json.loads(ln) for ln in handle.read().splitlines()
                    if ln.strip()]

    def close(self):
        self._temp.cleanup()


class ReloadDiscardTest(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()

    def tearDown(self):
        self.h.close()

    def test_clean_file_logs_nothing_and_stays(self):
        records = [_user("turn"), _assistant(_tool_call()),
                   _tool(), _assistant({"type": "text", "text": "done"},
                                       finish="stop")]
        self.h.write(records)
        loaded = self.h.reload()
        self.assertEqual([r["type"] for r in loaded],
                         ["user", "assistant", "tool", "assistant"])
        self.assertEqual(self.h.log_lines("dropped"), [])
        self.assertEqual(len(self.h.jsonl()), 4)

    def test_dangling_tool_round_is_dropped_and_logged(self):
        records = [_user("turn"), _assistant(_tool_call())]
        self.h.write(records)
        loaded = self.h.reload()
        self.assertEqual([r["type"] for r in loaded], ["user"])
        self.assertEqual(len(self.h.log_lines("dropped")), 1)
        self.assertTrue(self.h.log_lines("dropped")[0].endswith(
            "records=1"))
        self.assertEqual([r["type"] for r in self.h.jsonl()], ["user"])

    def test_half_finished_round_is_dropped_and_logged(self):
        records = [_user("turn"), _assistant(_tool_call("c1"),
                                             _tool_call("c2")),
                   _tool("c1")]
        self.h.write(records)
        loaded = self.h.reload()
        self.assertEqual([r["type"] for r in loaded], ["user"])
        self.assertTrue(self.h.log_lines("dropped")[0].endswith(
            "records=1"))

    def test_bad_json_line_is_dropped_and_logged(self):
        self.h.write_text(json.dumps(_user("turn")) + "\n{not json\n")
        loaded = self.h.reload()
        self.assertEqual([r["type"] for r in loaded], ["user"])
        self.assertTrue(self.h.log_lines("dropped")[0].endswith(
            "records=1"))

    def test_dangling_tool_tail_drops_plain(self):
        kept = _assistant(_tool_call("c9"), finish="stop")
        self.h.write([_user("earlier"), kept])
        loaded = self.h.reload()
        self.assertEqual([r["type"] for r in loaded], ["user"])
        self.assertEqual(self.h.log_lines("splice"), [])
        self.assertTrue(self.h.log_lines("dropped")[0].endswith(
            "records=1"))


if __name__ == "__main__":
    unittest.main()
