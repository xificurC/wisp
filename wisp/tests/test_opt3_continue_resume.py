"""Unit tests for `wisp continue`.

`wisp continue` finishes an open segment without appending a user
prompt, so the killed segment's rounds stay in the conversation as
plain history. A stop-finish assistant tail - a finished run - and
an empty log fail fast and name `wisp run`. The extensionless wisp
module imports by path, so the package stays stdlib only."""
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
    """Scripted turns; raises when the script runs out - the
    simulated kill of a later round."""

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


class _Stdin:
    """Fails on any read: `wisp continue` must read no stdin."""

    def read_text(self):
        raise AssertionError("wisp continue read stdin")


class _Http:
    """refresh_model_cfg stays best-effort: this one always fails."""

    def get_json(self, url, headers):
        raise IOError("no model info in tests")


class _Opts:
    def __init__(self, sessiondir):
        self.sessiondir = sessiondir


def _turn_tool():
    return {"finish_reason": "tool_calls",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                _tool_call()),
            "cached_tokens": 0}


def _turn_stop(text="done."):
    return {"finish_reason": "stop",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                {"type": "text", "text": text}),
            "cached_tokens": 0}


class _Harness:
    """One session dir plus a world wired for continue_agent_loop."""

    def __init__(self, temp):
        self.sessiondir = os.path.join(temp, "run-%s"
                                   % wisp.Rng(wisp.World({})).token())
        os.makedirs(self.sessiondir)
        setup = {"model": "m", "thinking": None}
        with open(os.path.join(self.sessiondir, "wisp.run.json"), "w") as h:
            json.dump(setup, h)
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            h.write("")
        with open(os.path.join(self.sessiondir, "wisp.usage"), "w") as h:
            h.write("")
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("stdin", _Stdin())
        self.world.set("http", _Http())
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "u",
                               "WISP_LLM_API_KEY": "k"})

    def seed(self, records):
        """Write records to wisp.jsonl as if a dead run committed
        them."""
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            for rec in records:
                h.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def continue_run(self, llm):
        """wisp continue on the seeded dir; a RuntimeError from an
        empty script is the simulated kill and unwinds the same
        flush path, so it propagates after the finally ran."""
        self.world.set("llm", llm)
        self.world.set("tools", _Tools())
        return wisp.continue_agent_loop(self.world, _Opts(self.sessiondir))

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def log_lines(self, tag):
        path = os.path.join(self.sessiondir, "wisp.log")
        if not os.path.exists(path):
            return []
        with open(path) as h:
            return [ln for ln in h.read().splitlines()
                    if " %s " % tag in ln]


def _tool_round(cid="c1"):
    return [_assistant({"type": "reasoning", "text": "think"},
                       _tool_call(cid)), _tool(cid)]


class ContinueRejectTest(unittest.TestCase):
    def test_finished_plain_run_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.seed([_user("turn"), _assistant(
                {"type": "text", "text": "done."})])
            with self.assertRaises(SystemExit):
                h.continue_run(_Llm([]))
            self.assertIn("run finished",
                          h.world.get("stderr").getvalue())

    def test_empty_log_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with self.assertRaises(SystemExit):
                h.continue_run(_Llm([]))
            self.assertIn("nothing to continue",
                          h.world.get("stderr").getvalue())

    def test_system_only_log_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.seed([{"type": "system", "content": "sys"}])
            with self.assertRaises(SystemExit):
                h.continue_run(_Llm([]))
            self.assertIn("nothing to continue",
                          h.world.get("stderr").getvalue())

    def test_open_plain_tail_runs(self):
        """A session with an open tail resumes: no prompt appended,
        the model finishes the turn."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.seed([_user("turn")] + _tool_round("c1"))
            h.continue_run(_Llm([{"finish_reason": "stop",
                                  "assistant": _assistant(
                                      {"type": "text",
                                       "text": "done."}),
                                  "cached_tokens": 0}]))
            recs = h.jsonl()
            self.assertEqual([r["type"] for r in recs],
                             ["user", "assistant", "tool",
                              "assistant"])
            self.assertEqual(len(h.log_lines("commit")), 1)


if __name__ == "__main__":
    unittest.main()
