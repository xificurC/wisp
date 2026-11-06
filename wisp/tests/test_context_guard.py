"""Unit tests for the run context guard: the --context-guard flag,
the round-boundary check in loop_rounds, exit 75 and the stop line.

`wisp run --context-guard LIMIT` stops the run at a round boundary
when the last round's prompt tokens cross the limit. '70%' is a
percent of the model's context window from wisp.modelcfg; '150k',
'1m' and a plain number are token limits. The stop exits 75
(GUARD_EXIT), writes one stderr line that names the next steps, and
leaves the session resumable: run, continue and steer all work on
it. The extensionless wisp module imports by path, so the package
stays stdlib only."""
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


def _assistant(*blocks, usage=None):
    rec = {"type": "assistant", "output": list(blocks)}
    if usage is not None:
        rec["usage"] = usage
    return rec


def _usage(prompt):
    return [{"prompt_tokens": prompt, "completion_tokens": 10,
             "total_tokens": prompt + 10}]


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
    """Scripted turns; each turn records the conversation it saw."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen = []

    def turn(self, records):
        self.seen.append([dict(rec) for rec in records])
        if not self.turns:
            raise RuntimeError("simulated kill mid-round")
        return self.turns.pop(0)


class _Tools:
    """Scripted tool runs; the hook runs where a live steer would
    queue, inside the round, past the run-start drain."""

    def __init__(self, hook=None):
        self.hook = hook

    def execute(self, calls):
        if self.hook:
            self.hook()
        return [_tool(c.get("id")) for c in calls]


class _Opts:
    def __init__(self, sessiondir, context_guard=None):
        self.sessiondir = sessiondir
        self.context_guard = context_guard


def _turn_tool(cid="c1", prompt=None):
    usage = _usage(prompt) if prompt is not None else None
    return {"finish_reason": "tool_calls",
            "assistant": _assistant(
                {"type": "reasoning", "text": "think"},
                _tool_call(cid), usage=usage),
            "cached_tokens": 0}


def _turn_stop(text="done", prompt=None):
    usage = _usage(prompt) if prompt is not None else None
    return {"finish_reason": "stop",
            "assistant": _assistant({"type": "text", "text": text},
                                    usage=usage),
            "cached_tokens": 0}


def _turn_unfinished(prompt=None):
    """A stream with no finish marker but with text: a turn end the
    degenerate guard passes, yet not a segment end - the loop keeps
    the round and asks again. The guard checks this boundary too."""
    usage = _usage(prompt) if prompt is not None else None
    return {"finish_reason": "",
            "assistant": _assistant({"type": "text", "text": "partial"},
                                    usage=usage),
            "cached_tokens": 0}


class _Harness:
    """One session dir plus a world wired for run and continue."""

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
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "http://u/v1/chat/completions",
                               "WISP_LLM_API_KEY": "k"})

    def modelcfg(self, window):
        """Write wisp.modelcfg with one context window for model m."""
        with open(os.path.join(self.sessiondir, "wisp.modelcfg"), "w") as h:
            json.dump({"m": {"context": window}}, h)

    def run(self, prompt, llm, guard=None, tools=None):
        """`wisp run` with the prompt on stdin; returns the rc."""
        self.world.set("stdin", _Stdin(prompt))
        self.world.set("llm", llm)
        self.world.set("tools", tools or _Tools())
        return wisp.run_agent_loop(
            self.world, _Opts(self.sessiondir, guard))

    def continue_run(self, llm, guard=None):
        """`wisp continue`; returns the rc."""
        self.world.set("llm", llm)
        self.world.set("tools", _Tools())
        return wisp.continue_agent_loop(
            self.world, _Opts(self.sessiondir, guard))

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def stderr(self):
        return self.world.get("stderr").getvalue()

    def seed(self, records):
        """Write records to wisp.jsonl as if a dead run committed
        them."""
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            for rec in records:
                h.write(json.dumps(rec, ensure_ascii=False) + "\n")


class ParseContextGuardTest(unittest.TestCase):
    def _parse(self, raw):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            spec = wisp.parse_context_guard(h.world, raw)
            h.world.get("stderr").getvalue()  # no fail means no output
            return spec

    def _fails(self, raw, message):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with self.assertRaises(SystemExit):
                wisp.parse_context_guard(h.world, raw)
            self.assertIn(message, h.stderr())

    def test_percent_form(self):
        self.assertEqual(self._parse("70%"),
                         {"kind": "percent", "value": 70})
        self.assertEqual(self._parse("1%"),
                         {"kind": "percent", "value": 1})
        self.assertEqual(self._parse("99%"),
                         {"kind": "percent", "value": 99})

    def test_token_forms(self):
        self.assertEqual(self._parse("150k"),
                         {"kind": "tokens", "value": 150000})
        self.assertEqual(self._parse("1m"),
                         {"kind": "tokens", "value": 1000000})
        self.assertEqual(self._parse("1M"),
                         {"kind": "tokens", "value": 1000000})
        self.assertEqual(self._parse("200000"),
                         {"kind": "tokens", "value": 200000})

    def test_bad_forms_fail(self):
        self._fails("70x", "--context-guard 70x")
        self._fails("foo", "--context-guard foo")
        self._fails("", "--context-guard : use a percent")
        self._fails("70k%", "a percent takes no k or m")
        self._fails("0%", "from 1 to 99")
        self._fails("100%", "from 1 to 99")
        self._fails("0", "positive number")
        self._fails("0k", "positive number")


DIR = "<dir>"  # placeholder the cases swap for the real session dir


class ParseArgsTest(unittest.TestCase):
    def test_run_accepts_the_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            cmd, opts = wisp.parse_args(
                h.world, ["run", "-d", h.sessiondir,
                          "--context-guard", "70%"])
            self.assertEqual(cmd, "run")
            self.assertEqual(opts.context_guard, "70%")

    def test_run_accepts_the_equals_form(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            cmd, opts = wisp.parse_args(
                h.world, ["run", "-d", h.sessiondir,
                          "--context-guard=150k"])
            self.assertEqual(opts.context_guard, "150k")

    def test_continue_accepts_the_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            cmd, opts = wisp.parse_args(
                h.world, ["continue", "-d", h.sessiondir,
                          "--context-guard", "150k"])
            self.assertEqual(cmd, "continue")
            self.assertEqual(opts.context_guard, "150k")

    def test_other_commands_reject_the_flag(self):
        cases = {
            "steer": ["steer", "-d", DIR, "--context-guard", "70%"],
            "usage": ["usage", "-d", DIR, "--context-guard", "70%"],
            "response": ["response", "-d", DIR, "--context-guard", "70%"],
            "render-past": ["render-past", "-d", DIR,
                            "--context-guard", "70%"],
            "new": ["new", "-m", "m", "--context-guard", "70%"],
        }
        for argv in cases.values():
            with tempfile.TemporaryDirectory() as temp:
                h = _Harness(temp)
                args = [arg if arg != DIR else h.sessiondir
                        for arg in argv]
                with self.assertRaises(SystemExit):
                    wisp.parse_args(h.world, args)
                self.assertIn("--context-guard is a flag of", h.stderr())

    def test_malformed_value_fails_at_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with self.assertRaises(SystemExit):
                wisp.parse_args(
                    h.world, ["run", "-d", h.sessiondir,
                              "--context-guard", "70x"])
            self.assertIn("--context-guard 70x", h.stderr())

    def test_missing_value_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with self.assertRaises(SystemExit):
                wisp.parse_args(
                    h.world, ["run", "-d", h.sessiondir,
                              "--context-guard"])
            self.assertIn("--context-guard needs a value", h.stderr())


class PercentGuardTest(unittest.TestCase):
    def test_fires_at_the_crossed_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=8000), _turn_stop()])
            rc = h.run("work", llm, guard="70%")
            self.assertEqual(rc, wisp.GUARD_EXIT)
            self.assertEqual(rc, 75)
            err = h.stderr()
            self.assertIn("context guard", err)
            self.assertIn(h.sessiondir, err)
            self.assertIn("round 1", err)
            self.assertIn("8.0k of 10k tokens (80.0%)", err)
            self.assertIn("70% (7.0k tokens)", err)
            self.assertIn("`wisp run`", err)
            self.assertIn("`wisp steer`", err)
            self.assertIn("do nothing", err)
            # The finished round stays on disk: user, assistant, tool.
            kinds = [rec["type"] for rec in h.jsonl()]
            self.assertEqual(kinds, ["user", "assistant", "tool"])
            # The guard fired once: the second scripted turn never ran.
            self.assertEqual(len(llm.seen), 1)

    def test_below_the_limit_runs_on(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=5000), _turn_stop()])
            rc = h.run("work", llm, guard="70%")
            self.assertEqual(rc, 0)
            self.assertNotIn("context guard", h.stderr())
            self.assertEqual(len(llm.seen), 2)

    def test_exact_cross_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=7000), _turn_stop()])
            rc = h.run("work", llm, guard="70%")
            self.assertEqual(rc, 75)

    def test_no_window_fails_at_start(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            # No wisp.modelcfg at all.
            with self.assertRaises(SystemExit):
                h.run("work", _Llm([_turn_stop()]), guard="70%")
            self.assertIn("no context window for model m", h.stderr())
            self.assertIn("--context-guard 150k", h.stderr())
            # Nothing ran: no prompt record reached the jsonl.
            self.assertEqual(h.jsonl(), [])

    def test_percent_copies_the_model_info_file_on_a_fresh_session(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            # No wisp.modelcfg at start; the file carries the table.
            infopath = os.path.join(temp, "models.json")
            with open(infopath, "w") as fh:
                json.dump({"m": {"context": 100000}}, fh)
            h.world.get("env")["WISP_LLM_MODEL_INFO_FILE"] = infopath
            rc = h.run("work",
                       _Llm([_turn_tool(prompt=7000), _turn_stop()]),
                       guard="5%")
            self.assertEqual(rc, 75)
            # The guard copied and wrote the modelcfg it needed.
            with open(os.path.join(h.sessiondir, "wisp.modelcfg")) as fh:
                table = json.loads(fh.read())
            self.assertEqual(table["m"]["context"], 100000)
            self.assertTrue(h.jsonl())

    def test_modelcfg_without_context_fails_at_start(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            with open(os.path.join(h.sessiondir, "wisp.modelcfg"),
                      "w") as fh:
                json.dump({"m": {"input": 1}}, fh)
            with self.assertRaises(SystemExit):
                h.run("work", _Llm([_turn_stop()]), guard="70%")
            self.assertIn("no context window for model m", h.stderr())

    def test_round_without_usage_skips_the_check(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(), _turn_stop()])
            rc = h.run("work", llm, guard="70%")
            self.assertEqual(rc, 0)
            self.assertNotIn("context guard", h.stderr())


class TokenGuardTest(unittest.TestCase):
    def test_k_limit_fires(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)  # enriches the stop line only
            llm = _Llm([_turn_tool(prompt=9500), _turn_stop()])
            rc = h.run("work", llm, guard="9k")
            self.assertEqual(rc, 75)
            self.assertIn("9.5k of 10k tokens (95.0%)", h.stderr())
            self.assertIn("9.0k tokens", h.stderr())

    def test_plain_number_limit_fires(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            llm = _Llm([_turn_tool(prompt=9500), _turn_stop()])
            rc = h.run("work", llm, guard="9000")
            self.assertEqual(rc, 75)

    def test_m_limit_allows_a_big_round(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            llm = _Llm([_turn_tool(prompt=9500), _turn_stop()])
            rc = h.run("work", llm, guard="1m")
            self.assertEqual(rc, 0)
            self.assertNotIn("context guard", h.stderr())

    def test_no_modelcfg_needed(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            # No wisp.modelcfg: token mode never reads it to decide.
            llm = _Llm([_turn_tool(prompt=100), _turn_stop()])
            rc = h.run("work", llm, guard="1k")
            self.assertEqual(rc, 0)


class BoundaryTest(unittest.TestCase):
    def test_unfinished_stream_boundary_checks_too(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_unfinished(prompt=8000), _turn_stop()])
            rc = h.run("work", llm, guard="70%")
            self.assertEqual(rc, 75)
            self.assertIn("round 1", h.stderr())

    def test_steer_warning_still_runs_after_the_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)

            def queue_late_steer():
                h.world.set("stdin", _Stdin("late message"))
                wisp.steer_command(h.world, _Opts(h.sessiondir))

            tools = _Tools(hook=queue_late_steer)
            llm = _Llm([_turn_tool(prompt=8000), _turn_stop()])
            rc = h.run("work", llm, guard="70%", tools=tools)
            self.assertEqual(rc, 75)
            self.assertIn("steer message(s) never injected", h.stderr())


class ResumeTest(unittest.TestCase):
    def test_continue_finishes_after_a_guard_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=8000), _turn_stop()])
            self.assertEqual(h.run("work", llm, guard="70%"), 75)
            rc = h.continue_run(_Llm([_turn_stop()]))
            self.assertEqual(rc, 0)
            kinds = [rec["type"] for rec in h.jsonl()]
            self.assertEqual(kinds,
                             ["user", "assistant", "tool", "assistant"])

    def test_continue_carries_its_own_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            h.seed([{"type": "user", "content": "work"},
                    _assistant(_tool_call("c1"), usage=_usage(3000)),
                    _tool("c1")])
            llm = _Llm([_turn_tool(prompt=9500), _turn_stop()])
            rc = h.continue_run(llm, guard="9k")
            self.assertEqual(rc, 75)
            self.assertIn("round 1", h.stderr())
            # The continue round committed before the stop.
            kinds = [rec["type"] for rec in h.jsonl()]
            self.assertEqual(
                kinds, ["user", "assistant", "tool",
                        "assistant", "tool"])

    def test_run_resumes_after_a_guard_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=8000), _turn_stop()])
            self.assertEqual(h.run("work", llm, guard="70%"), 75)
            # A plain run without the guard picks the session up.
            rc = h.run("more", _Llm([_turn_stop()]))
            self.assertEqual(rc, 0)
            kinds = [rec["type"] for rec in h.jsonl()]
            self.assertEqual(
                kinds, ["user", "assistant", "tool",
                        "user", "assistant"])

    def test_guard_line_lands_in_the_log(self):
        with tempfile.TemporaryDirectory() as temp:
            h = _Harness(temp)
            h.modelcfg(10000)
            llm = _Llm([_turn_tool(prompt=8000), _turn_stop()])
            self.assertEqual(h.run("work", llm, guard="70%"), 75)
            with open(os.path.join(h.sessiondir, "wisp.log")) as fh:
                log = fh.read()
            self.assertIn("guard", log)
            self.assertIn("used=8000", log)


if __name__ == "__main__":
    unittest.main()
