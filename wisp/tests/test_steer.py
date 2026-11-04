"""Unit tests for the steer mailbox: `wisp steer`, the round-boundary
drain, the segment rule and the end-of-run warning.

`wisp steer` appends one JSON line to <DIR>/wisp.steer.inbox. A live
run renames the inbox away at each round boundary and turns its lines
into steered user records, marked wisp_steered: plain user records on
the wire that never open a segment. A run that ends with messages
still waiting warns on stderr; the next `wisp run` drains the stale
inbox before its prompt. The extensionless wisp module imports by
path, so the package stays stdlib only."""
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


def _user(content, steered=False):
    rec = {"type": "user", "content": content}
    if steered:
        rec["wisp_steered"] = True
    return rec


def _tool(cid="c1"):
    return {"type": "tool", "call_id": cid, "name": "bash",
            "content": "x", "exit": 0}


class _Stdin:
    """One canned stdin text."""

    def __init__(self, text=""):
        self._text = text

    def read_text(self):
        return self._text

    def lines(self):
        return iter(self._text.splitlines())

    def is_interactive(self):
        return False


class _Llm:
    """Scripted turns; each turn records the conversation it saw. The
    hook runs inside turn(), the place a live steer would land."""

    def __init__(self, turns, hook=None):
        self.turns = list(turns)
        self.seen = []
        self.hook = hook

    def turn(self, records):
        self.seen.append([dict(rec) for rec in records])
        if self.hook:
            self.hook()
        if not self.turns:
            raise RuntimeError("simulated kill mid-round")
        return self.turns.pop(0)


class _Tools:
    """Scripted tool runs; the hook runs where a steer would queue."""

    def __init__(self, hook=None):
        self.hook = hook

    def execute(self, calls):
        if self.hook:
            self.hook()
        return [_tool(c.get("id")) for c in calls]


class _Http:
    """refresh_model_cfg stays best-effort: this one always fails."""

    def get_json(self, url, headers):
        raise IOError("no model info in tests")


class _Opts:
    def __init__(self, sessiondir):
        self.sessiondir = sessiondir


def _turn_tool(cid="c1"):
    return {"finish_reason": "tool_calls",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                _tool_call(cid)),
            "cached_tokens": 0}


def _turn_stop(text="done"):
    return {"finish_reason": "stop",
            "assistant": _assistant({"type": "text", "text": text}),
            "cached_tokens": 0}


class _Harness:
    """One session dir plus a world wired for steer, run and continue."""

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
        self.world.set("rng", wisp.Rng(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("http", _Http())
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "u",
                               "WISP_LLM_API_KEY": "k"})

    # -- command drivers -------------------------------------------------

    def steer(self, message):
        """`wisp steer` with the message on stdin; returns the rc."""
        self.world.set("stdin", _Stdin(message))
        return wisp.steer_command(self.world, _Opts(self.sessiondir))

    def run(self, prompt, llm, tools=None):
        """`wisp run` with the prompt on stdin."""
        self.world.set("stdin", _Stdin(prompt))
        self.world.set("llm", llm)
        self.world.set("tools", tools or _Tools())
        return wisp.run_agent_loop(self.world, _Opts(self.sessiondir))

    def continue_run(self, llm, tools=None):
        """`wisp continue`; a RuntimeError from an empty script is the
        simulated kill and unwinds the same flush path."""
        self.world.set("llm", llm)
        self.world.set("tools", tools or _Tools())
        return wisp.continue_agent_loop(self.world, _Opts(self.sessiondir))

    # -- inspection ------------------------------------------------------

    def inbox(self):
        return os.path.join(self.sessiondir, "wisp.steer.inbox")

    def inbox_lines(self):
        if not os.path.exists(self.inbox()):
            return []
        with open(self.inbox()) as h:
            return [ln for ln in h.read().splitlines() if ln.strip()]

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def stderr(self):
        return self.world.get("stderr").getvalue()

    def stdout(self):
        return self.world.get("stdout").getvalue()

    def seed(self, records):
        """Write records to wisp.jsonl as if a dead run committed
        them."""
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            for rec in records:
                h.write(json.dumps(rec, ensure_ascii=False) + "\n")


class SteerCommandTest(unittest.TestCase):
    def test_queues_one_json_line(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            self.assertEqual(h.steer("but check the tests\n"), 0)
            lines = h.inbox_lines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]),
                             {"content": "but check the tests"})

    def test_messages_stack_in_order(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.steer("first")
            h.steer("second\nmulti line")
            lines = h.inbox_lines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["content"], "first")
            self.assertEqual(json.loads(lines[1])["content"],
                             "second\nmulti line")

    def test_empty_message_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with self.assertRaises(SystemExit):
                h.steer("  \n")
            self.assertIn("no steer message on stdin", h.stderr())
            self.assertEqual(h.inbox_lines(), [])

    def test_logs_the_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.steer("note")
            with open(os.path.join(h.sessiondir, "wisp.log")) as f:
                self.assertIn(" steer queued=1", f.read())


class SteerIntakeTest(unittest.TestCase):
    def _prepared(self, temp, records):
        h = _Harness(temp)
        h.seed(records)
        h.world.set("committed", len(records))
        loaded = h.jsonl()
        return h, loaded

    def test_no_inbox_is_a_noop(self):
        with tempfile.TemporaryDirectory() as temp:
            h, records = self._prepared(temp, [_user("turn")])
            self.assertEqual(wisp.steer_intake(h.world, records), 0)
            self.assertEqual(len(records), 1)

    def test_drains_records_and_flushes(self):
        with tempfile.TemporaryDirectory() as temp:
            h, records = self._prepared(temp, [_user("turn")])
            h.steer("one")
            h.steer("two")
            count = wisp.steer_intake(h.world, records)
            self.assertEqual(count, 2)
            self.assertEqual([r["content"] for r in records[1:]],
                             ["one", "two"])
            self.assertTrue(all(r.get("wisp_steered") for r in records[1:]))
            # the drain commits: the jsonl holds the steered records
            self.assertEqual([r["content"] for r in h.jsonl()[1:]],
                             ["one", "two"])
            # the inbox is gone, and no consumed copy stays behind
            self.assertFalse(os.path.exists(h.inbox()))
            leftovers = [n for n in os.listdir(h.sessiondir)
                         if n.startswith("wisp.steer.inbox.")]
            self.assertEqual(leftovers, [])

    def test_stream_line_and_log(self):
        with tempfile.TemporaryDirectory() as temp:
            h, records = self._prepared(temp, [_user("turn")])
            h.steer("redirect")
            wisp.steer_intake(h.world, records)
            self.assertIn('"wisp": "steer"', h.stdout())
            self.assertIn("redirect", h.stdout())
            with open(os.path.join(h.sessiondir, "wisp.log")) as f:
                self.assertIn(" steer injected=1", f.read())

    def test_partial_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            h, records = self._prepared(temp, [_user("turn")])
            h.steer("good")
            with open(h.inbox(), "a") as f:
                f.write('{"content": "half')  # a mid-append kill remnant
            count = wisp.steer_intake(h.world, records)
            self.assertEqual(count, 1)
            self.assertEqual(records[-1]["content"], "good")

    def test_non_string_content_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            h, records = self._prepared(temp, [_user("turn")])
            with open(h.inbox(), "w") as f:
                f.write(json.dumps({"content": 7}) + "\n")
            self.assertEqual(wisp.steer_intake(h.world, records), 0)
            self.assertEqual(len(records), 1)


class LiveDrainTest(unittest.TestCase):
    def test_steer_between_rounds_reaches_the_next_turn(self):
        """The core case: a steer queued while round 1 runs its tools
        lands before round 2's llm.turn, as a committed user record."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            tools = _Tools(hook=lambda: h.steer("but check the tests"))
            llm = _Llm([_turn_tool(), _turn_stop("ok")])
            h.run("go", llm, tools)
            # round 2 saw the steered record after the tool records
            seen = llm.seen[1]
            kinds = [r["type"] for r in seen]
            self.assertEqual(kinds, ["user", "assistant", "tool", "user"])
            self.assertEqual(seen[-1]["content"], "but check the tests")
            self.assertTrue(seen[-1].get("wisp_steered"))
            # the record committed, and the stream carried the steer
            self.assertEqual(h.jsonl()[3]["content"], "but check the tests")
            self.assertIn('"wisp": "steer"', h.stdout())

    def test_stale_inbox_drains_before_the_new_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.steer("remember the constraint")
            llm = _Llm([_turn_stop("ok")])
            h.run("go", llm)
            seen = llm.seen[0]
            self.assertEqual([r["content"] for r in seen],
                             ["remember the constraint", "go"])
            self.assertEqual([r["content"] for r in h.jsonl()[:2]],
                             ["remember the constraint", "go"])

    def test_continue_resume_drains_a_stale_inbox(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.seed([_user("turn"), _assistant(_tool_call("c1")),
                    _tool("c1")])
            h.steer("while you were gone")
            llm = _Llm([_turn_stop("ok")])
            h.continue_run(llm)
            seen = llm.seen[0]
            self.assertEqual(seen[-1]["content"], "while you were gone")
            self.assertTrue(seen[-1].get("wisp_steered"))


class EndWarningTest(unittest.TestCase):
    def test_warning_when_messages_wait_past_the_end(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            llm = _Llm([_turn_stop()],
                       hook=lambda: h.steer("too late"))
            h.run("go", llm)
            self.assertIn("1 steer message(s) never injected", h.stderr())
            self.assertIn("wisp.steer.inbox", h.stderr())
            self.assertEqual(len(h.inbox_lines()), 1)

    def test_no_warning_when_all_injected(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            tools = _Tools(hook=lambda: h.steer("in time"))
            llm = _Llm([_turn_tool(), _turn_stop()])
            h.run("go", llm, tools)
            self.assertNotIn("steer message(s) never injected",
                             h.stderr())
            self.assertEqual(h.inbox_lines(), [])

    def test_warning_counts_only_complete_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with open(h.inbox(), "w") as f:
                f.write('{"content": "a full message"}\n')
                f.write('{"content": "half')
            wisp.warn_undelivered_steer(h.world)
            self.assertIn("1 steer message(s) never injected", h.stderr())

    def test_warning_fires_through_a_simulated_kill(self):
        """The steer queues while the only round runs, the round dies,
        and the exit path still warns: the finally owns the warning."""
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            llm = _Llm([], hook=lambda: h.steer("queued then killed"))
            with self.assertRaises(RuntimeError):
                h.run("go", llm)
            self.assertIn("1 steer message(s) never injected", h.stderr())


class ReplayTest(unittest.TestCase):
    def test_stored_steer_replays_with_its_marker(self):
        records = [_user("turn"), _user("redirect", steered=True)]
        lines = list(wisp.records_to_stream(records))
        payloads = [json.loads(ln[len("data: "):]) for ln in lines]
        steers = [p for p in payloads if p.get("wisp") == "steer"]
        self.assertEqual(len(steers), 1)
        self.assertEqual(steers[0]["content"], "redirect")
        prompts = [p for p in payloads if p.get("wisp") == "prompt"]
        self.assertEqual(len(prompts), 1)  # the plain prompt stays a prompt

    def test_renderer_prints_the_steer_marker(self):
        h_world = wisp.World({})
        h_world.set("stdout", io.StringIO())
        h_world.set("env", {})
        renderer = wisp.Renderer(h_world)
        for line in wisp.records_to_stream(
                [_user("redirect", steered=True)]):
            renderer.render_line(line)
        renderer.finish()
        out = h_world.get("stdout").getvalue()
        self.assertIn("[steer]\nredirect", out)


class ArgParsingTest(unittest.TestCase):
    def _world(self):
        world = wisp.World({})
        world.set("stderr", io.StringIO())
        world.set("stdout", io.StringIO())
        world.set("fs", wisp.Fs(world))
        world.set("env", {})
        return world

    def test_steer_binds_the_session_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            world = self._world()
            cmd, opts = wisp.parse_args(
                world, ["steer", "-d", h.sessiondir])
            self.assertEqual(cmd, "steer")
            self.assertEqual(opts.sessiondir, h.sessiondir)

    def test_steer_rejects_model_flags(self):
        world = self._world()
        with self.assertRaises(SystemExit):
            wisp.parse_args(world, ["steer", "-m", "x"])
        self.assertIn("takes only -d", world.get("stderr").getvalue())

    def test_steer_needs_a_session_dir(self):
        world = self._world()
        with self.assertRaises(SystemExit):
            wisp.parse_args(world, ["steer"])
        self.assertIn("pass -d DIR", world.get("stderr").getvalue())


class WireTagTest(unittest.TestCase):
    """Spec-003 amendment: build_request tags steered user messages,
    so the model can tell steering from the turn prompt."""

    def test_tag_marks_only_steered_messages(self):
        world = wisp.World({})
        world.set("model", "m")
        world.set("thinking", None)
        records = [
            {"type": "user", "content": "do the thing"},
            _user("but avoid /tmp", steered=True),
        ]
        body = wisp.build_request(world, records)
        prompt, steer = (m["content"] for m in body["messages"])
        self.assertEqual(prompt, "do the thing")
        self.assertTrue(steer.startswith(wisp.STEER_TAG))
        self.assertIn("but avoid /tmp", steer)

if __name__ == "__main__":
    unittest.main()
