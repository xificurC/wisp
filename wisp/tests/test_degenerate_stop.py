"""Unit tests for the degenerate empty-stop guard in loop_rounds.

A degenerate turn: a result with no text block and no tool-call
block - a stop after thinking only, or an empty completion, whatever
usage it carries. A turn ends only on text or tool calls. A textless
result is not a turn end: the record is appended (the thinking rides
the next request and survives on disk) and the model is asked again,
at most WISP_DEGENERATE_RETRY attempts (default 3) before the run
fails. The extensionless wisp module
imports by path, so the package stays stdlib only."""
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

NUDGE = "Continue where you left off"


def _tool_call(cid="c1"):
    return {"type": "tool_call", "id": cid, "name": "bash",
            "arguments": "{\"command\":\"echo x\"}"}


def _tool(cid="c1"):
    return {"type": "tool", "call_id": cid, "name": "bash",
            "content": "x", "exit": 0}


def _turn(blocks, finish, usage=None):
    return {"finish_reason": finish, "cached_tokens": 0,
            "assistant": {"type": "assistant", "output": list(blocks),
                          "finish_reason": finish,
                          "usage": usage or []}}


def _degenerate(finish="stop"):
    return _turn([], finish)


def _empty_with_usage():
    return _turn([], "stop", usage=[{"total_tokens": 7}])


def _reasoning_only(usage=None):
    """A stop with only thinking: the 2026-10-07 failure mode."""
    return _turn([{"type": "reasoning", "text": "think"}], "stop",
                 usage=usage)


def _answer(text="answer."):
    return _turn([{"type": "reasoning", "text": "think"},
                  {"type": "text", "text": text}], "stop",
                 usage=[{"total_tokens": 9}])


def _tool_turn():
    return _turn([{"type": "reasoning", "text": "think"},
                  _tool_call()], "tool_calls")


class _Llm:
    """Scripted turns; one degenerate replay counter for retries."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0
        self.seen = []

    def turn(self, records):
        self.calls += 1
        self.seen.append([dict(r) for r in records])
        if not self.turns:
            raise AssertionError("script ran out")
        return self.turns.pop(0)


class _Tools:
    def __init__(self):
        self.calls = []

    def execute(self, calls):
        self.calls.extend(calls)
        return [_tool(c.get("id")) for c in calls]


class _Stdin:
    def read_text(self):
        raise AssertionError("loop_rounds reads no stdin")


class _Http:
    def get_json(self, url, headers):
        raise IOError("no model info in tests")


class _Harness:
    """One session dir plus a world wired for loop_rounds."""

    def __init__(self):
        import tempfile
        self._temp = tempfile.TemporaryDirectory()
        self.sessiondir = os.path.join(self._temp.name, "run")
        os.makedirs(self.sessiondir)
        with open(os.path.join(self.sessiondir, "wisp.jsonl"), "w") as h:
            h.write("")
        with open(os.path.join(self.sessiondir, "wisp.usage"), "w") as h:
            h.write("")
        self.world = wisp.World({})
        self.world.set("fs", wisp.Fs(self.world))
        self.world.set("clock", wisp.Clock(self.world))
        self.world.set("session", wisp.Session(self.world))
        self.world.set("stderr", io.StringIO())
        self.world.set("stdout", io.StringIO())
        self.world.set("stdin", _Stdin())
        self.world.set("http", _Http())
        self.world.set("sessiondir", self.sessiondir)
        self.world.set("env", {"WISP_LLM_URL": "u",
                               "WISP_LLM_API_KEY": "k"})
        self.world.set("model", "m")
        self.world.set("thinking", None)
        self.world.set("committed", 0)
        self.llm = _Llm([])
        self.world.set("llm", self.llm)
        self.world.set("tools", _Tools())

    def run(self, turns, max_rounds=10):
        self.llm = _Llm(turns)
        self.world.set("llm", self.llm)
        records = [{"type": "user", "content": "turn"}]
        wisp.loop_rounds(self.world, records, max_rounds, None)
        return records

    def stderr(self):
        return self.world.get("stderr").getvalue()

    def log_lines(self, tag):
        path = os.path.join(self.sessiondir, "wisp.log")
        if not os.path.exists(path):
            return []
        with open(path) as h:
            return [ln for ln in h.read().splitlines()
                    if " %s " % tag in ln]

    def jsonl(self):
        with open(os.path.join(self.sessiondir, "wisp.jsonl")) as h:
            return [json.loads(ln) for ln in h.read().splitlines()
                    if ln.strip()]

    def close(self):
        self._temp.cleanup()


class DegenerateStopTest(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()

    def tearDown(self):
        self.h.close()

    def test_retries_then_accepts_good_turn(self):
        records = self.h.run([_degenerate(), _degenerate(), _answer()])
        self.assertEqual(self.h.llm.calls, 3)
        self.assertEqual(len(self.h.log_lines("retry")), 2)
        tail = self.h.jsonl()[-1]
        self.assertEqual(tail["type"], "assistant")
        self.assertIn("answer.", tail["output"][-1]["text"])
        self.assertIsNone(tail.get("wisp_compaction_archive"))

    def test_all_retries_empty_fails_and_writes_only_nudges(self):
        with self.assertRaises(SystemExit) as caught:
            self.h.run([_degenerate()] * 3)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("empty or textless stop response", self.h.stderr())
        self.assertEqual(
            len(self.h.log_lines("degenerate")), 1)
        self.assertTrue(self.h.log_lines("degenerate")[0].endswith(
            "round=1 finish_reason=stop blocks=none usage_chunks=0"))
        self.assertEqual(len(self.h.log_lines("retry")), 2)
        self.assertEqual(self.h.llm.calls, 3)
        # each retry appended only its user nudge; no empty turn record
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "user", "user"])
        self.assertEqual([r.get("content") for r in self.h.jsonl()][1:],
                         [NUDGE, NUDGE])

    def test_reasoning_only_stop_is_retried_then_accepted(self):
        records = self.h.run([_reasoning_only(), _reasoning_only(),
                              _answer()])
        # the thinking rounds stay in the conversation as records
        self.assertEqual(len(records), 6)
        self.assertEqual(len(self.h.log_lines("retry")), 2)
        self.assertIn("blocks=reasoning", self.h.log_lines("retry")[0])
        self.assertEqual(self.h.log_lines("emptyturn"), [])
        self.assertEqual(self.h.log_lines("degenerate"), [])
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "assistant", "user", "assistant",
                          "user", "assistant"])

    def test_textless_stop_appends_thinking_and_resends(self):
        """The 2026-10-08 rule: a thinking block is not a turn end.
        The record stays, and the next request carries it."""
        self.h.run([_reasoning_only(), _answer()])
        self.assertEqual(self.h.llm.calls, 2)
        second = self.h.llm.seen[1]
        self.assertEqual(second[-1]["type"], "user")
        self.assertEqual(second[-1]["content"], NUDGE)
        self.assertEqual(second[-2]["type"], "assistant")
        self.assertEqual(second[-2]["output"][0]["type"], "reasoning")

    def test_degenerate_retry_env_bounds_attempts(self):
        """WISP_DEGENERATE_RETRY=1 fails on the first textless try."""
        self.h.world.get("env")["WISP_DEGENERATE_RETRY"] = "1"
        with self.assertRaises(SystemExit):
            self.h.run([_reasoning_only()] * 3)
        self.assertEqual(self.h.llm.calls, 1)
        self.assertEqual(len(self.h.log_lines("retry")), 0)
        self.assertEqual(len(self.h.log_lines("degenerate")), 1)

    def test_reasoning_only_with_usage_fails_after_retries(self):
        """Usage never rescues a textless turn: the acceptance branch
        is gone. The appended thinking stays on disk for the resume."""
        with self.assertRaises(SystemExit) as caught:
            self.h.run([_reasoning_only(usage=[{"total_tokens": 9}])] * 3)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("empty or textless stop response", self.h.stderr())
        self.assertEqual(len(self.h.log_lines("retry")), 2)
        self.assertEqual(len(self.h.log_lines("degenerate")), 1)
        self.assertEqual(len(self.h.log_lines("emptyturn")), 0)
        # every textless attempt appended its thinking record
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "assistant", "user", "assistant",
                          "user", "assistant"])

    def test_empty_with_usage_fails_and_writes_only_nudges(self):
        """An empty completion with usage is just as textless: the run
        fails and only the retry nudges reach the jsonl."""
        with self.assertRaises(SystemExit) as caught:
            self.h.run([_empty_with_usage()] * 3)
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(self.h.llm.calls, 3)
        self.assertEqual(len(self.h.log_lines("retry")), 2)
        self.assertEqual(len(self.h.log_lines("degenerate")), 1)
        self.assertEqual(len(self.h.log_lines("emptyturn")), 0)
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "user", "user"])

    def test_plain_session_also_fails_on_degenerate(self):
        with self.assertRaises(SystemExit):
            self.h.run([_degenerate()] * 3)
        self.assertIn("empty or textless stop response", self.h.stderr())
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "user", "user"])

    def test_content_turn_never_retries(self):
        records = self.h.run([_answer()])
        self.assertEqual(self.h.llm.calls, 1)
        self.assertEqual(len(self.h.log_lines("retry")), 0)

    def test_tool_round_then_degenerate_then_answer(self):
        records = self.h.run([_tool_turn(), _degenerate(), _answer()])
        self.assertEqual(self.h.llm.calls, 3)
        self.assertEqual(len(self.h.log_lines("retry")), 1)
        # the tool round stays, and the retry nudge follows its result
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "assistant", "tool", "user", "assistant"])

    def test_empty_text_blocks_count_as_degenerate(self):
        blank = _turn([{"type": "text", "text": "   "}], "stop")
        with self.assertRaises(SystemExit):
            self.h.run([blank] * 3)
        self.assertEqual(len(self.h.log_lines("degenerate")), 1)

    def test_stop_with_tool_calls_runs_tools_and_continues(self):
        """Some endpoints end a tool-bearing stream with stop. The
        tool calls decide: they run, the loop goes on."""
        records = self.h.run([_turn([_tool_call()], "stop"), _answer()])
        self.assertEqual(self.h.llm.calls, 2)
        self.assertEqual(len(self.h.world.get("tools").calls), 1)
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "assistant", "tool", "assistant"])

    def test_no_finish_marker_with_tool_calls_runs_tools(self):
        """A stream cut before the finish chunk still ran its tool
        calls; the loop must run them too."""
        records = self.h.run([_turn([_tool_call()], ""), _answer()])
        self.assertEqual(self.h.llm.calls, 2)
        self.assertEqual(len(self.h.world.get("tools").calls), 1)

    def test_no_finish_marker_with_text_continues_loop(self):
        """A stream cut mid-text is not a turn end: the round stays
        and the model is asked again."""
        records = self.h.run(
            [_turn([{"type": "text", "text": "partial"}], ""), _answer()])
        self.assertEqual(self.h.llm.calls, 2)
        self.assertIn("partial",
                      "".join(b.get("text", "") for r in self.h.jsonl()
                              for b in (r.get("output") or [])))

    def test_plain_no_finish_marker_keeps_round_on_disk(self):
        records = self.h.run(
            [_turn([{"type": "text", "text": "partial"}], ""), _answer()])
        types = [r["type"] for r in self.h.jsonl()]
        self.assertEqual(types, ["user", "assistant", "assistant"])

    def test_no_finish_marker_empty_fails_even_with_usage(self):
        """A stream that never said how it ended is broken: usage
        alone does not make an accepted empty turn."""
        blank = _turn([], "", usage=[{"total_tokens": 5}])
        with self.assertRaises(SystemExit):
            self.h.run([blank] * 3)
        self.assertEqual(len(self.h.log_lines("degenerate")), 1)
        self.assertEqual(len(self.h.log_lines("emptyturn")), 0)
        self.assertIn("<none>", self.h.stderr())
        self.assertEqual([r["type"] for r in self.h.jsonl()],
                         ["user", "user", "user"])


class _EmptySseHttp:
    """A real-looking SSE stream that carries only its done marker."""

    def __init__(self):
        self.posts = 0

    def post_stream(self, url, headers, body, meta=None):
        self.posts += 1
        if meta is not None:
            meta["status"] = 200
            meta["request_id"] = "req-empty"
        for line in ("", "data: {}"):
            yield line

    def get_json(self, url, headers):
        raise IOError("no model info in tests")


class EmptySseStreamTest(unittest.TestCase):
    """The litellm fault of 2026-10-20, end to end through the Llm."""

    def setUp(self):
        self.h = _Harness()

    def tearDown(self):
        self.h.close()

    def test_empty_stream_is_retried_with_nudge_and_names_cause(self):
        http = _EmptySseHttp()
        self.h.world.set("http", http)
        self.h.world.set("llm", wisp.Llm(self.h.world))
        with self.assertRaises(SystemExit) as caught:
            wisp.loop_rounds(
                self.h.world, [{"type": "user", "content": "turn"}], 10, None)
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(http.posts, 3)
        self.assertIn("no completion payload", self.h.stderr())
        self.assertIn("request id: req-empty", self.h.stderr())
        self.assertEqual(len(self.h.log_lines("streamfail")), 3)
        self.assertIn("sse=yes", self.h.log_lines("streamfail")[0])
        self.assertIn("note=", self.h.log_lines("degenerate")[0])
        self.assertEqual([r.get("content") for r in self.h.jsonl()][1:],
                         [NUDGE, NUDGE])


if __name__ == "__main__":
    unittest.main()
