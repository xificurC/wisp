"""Unit tests for per-round durability.

Every completed round commits raw, so a simulated mid-segment kill
keeps the finished rounds on disk; the next run loads them as plain
history. The tests follow the Option 2 design; the extensionless
wisp module imports by path, so the package stays stdlib only."""
import importlib.machinery
import importlib.util
import io
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


def _assistant(*blocks):
    return {"type": "assistant", "output": list(blocks)}


def _user(content):
    return {"type": "user", "content": content}


def _tool(cid="c1"):
    return {"type": "tool", "call_id": cid, "name": "bash",
            "content": "x", "exit": 0}


class _Llm:
    """Scripted turns; raises when the script runs out."""

    def __init__(self, turns):
        self.turns = list(turns)

    def turn(self, records):
        if not self.turns:
            raise RuntimeError("simulated kill mid-round")
        return self.turns.pop(0)


class _Tools:
    def __init__(self):
        self.calls = []

    def execute(self, calls):
        self.calls.extend(calls)
        return [_tool(c.get("id")) for c in calls]


def _turn_tool():
    return {"finish_reason": "tool_calls",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                _tool_call()),
            "cached_tokens": 0}


def _turn_stop(text="done"):
    return {"finish_reason": "stop",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                {"type": "text", "text": text}),
            "cached_tokens": 0}


class _Harness:
    """One session dir plus a world wired for loop_rounds."""

    def __init__(self, temp):
        self.sessiondir = os.path.join(temp, "run-%s"
                                   % wisp.Rng(wisp.World({})).token())
        os.makedirs(self.sessiondir)
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("model", "m")
        self.world.set("thinking", None)
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "http://u/v1/chat/completions",
                               "WISP_LLM_API_KEY": "k"})
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            h.write("")
        with open(os.path.join(self.sessiondir, "wisp.usage"), "w") as h:
            h.write("")

    def load(self):
        records, committed = self.world.get("session").load_events()
        self.world.set("committed", committed)
        return records

    def run(self, records, llm, max_rounds=10):
        self.world.set("llm", llm)
        self.world.set("tools", _Tools())
        try:
            wisp.loop_rounds(self.world, records, max_rounds)
            return 0
        except RuntimeError as exc:
            return exc  # the simulated kill; the finally still flushed
        finally:
            wisp.flush_records(self.world, records)

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def log_lines(self, tag):
        with open(os.path.join(self.sessiondir, "wisp.log")) as h:
            return [ln for ln in h.read().splitlines()
                    if " %s " % tag in ln]


class PerRoundDurabilityTest(unittest.TestCase):
    def test_two_round_run_commits_per_round(self):
        """A plain two-round run commits per round and never
        rewrites."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            records = h.load()
            records.append(_user("turn"))
            h.run(records, _Llm([_turn_tool(), _turn_stop()]))
            recs = h.jsonl()
            self.assertEqual([r["type"] for r in recs],
                             ["user", "assistant", "tool", "assistant"])
            self.assertEqual(len(h.log_lines("commit")), 2)
            self.assertEqual(len(h.log_lines("rewrite")), 0)

    def test_kill_mid_segment_keeps_raw_rounds(self):
        """A kill in round 2 leaves round 1 on disk; the exit commit
        flushes it and nothing duplicates."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            records = h.load()
            records.append(_user("turn"))
            h.run(records, _Llm([_turn_tool()]))
            recs = h.jsonl()
            self.assertEqual([r["type"] for r in recs],
                             ["user", "assistant", "tool"])
            self.assertEqual(len(h.log_lines("commit")), 1)

    def test_resume_keeps_raw_rounds_as_history(self):
        """After a mid-segment kill the next run loads the raw rounds
        and keeps them as plain history before its own prompt."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            records = h.load()
            records.append(_user("turn"))
            h.run(records, _Llm([_turn_tool()]))
            records = h.load()
            self.assertEqual([r["type"] for r in records],
                             ["user", "assistant", "tool"])
            records.append(_user("new turn"))
            h.run(records, _Llm([_turn_stop()]))
            recs = h.jsonl()
            self.assertEqual([r["type"] for r in recs],
                             ["user", "assistant", "tool",
                              "user", "assistant"])
            self.assertNotIn("wisp_compaction_archive", recs[-1])
            self.assertEqual(len(h.log_lines("rewrite")), 0)


if __name__ == "__main__":
    unittest.main()
