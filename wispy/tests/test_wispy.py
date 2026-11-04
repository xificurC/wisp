#!/usr/bin/env python3
"""Model-free tests for wispy.

Every test swaps the world: the filesystem, the child runner, the
environment, the streams, and the signal flag. The command handlers, the
phase machine, and the prompt assembly run for real.
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "wispy")


def load_module():
    loader = importlib.machinery.SourceFileLoader("wispy_under_test", SCRIPT)
    spec = importlib.util.spec_from_loader("wispy_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wispy_under_test"] = module
    loader.exec_module(module)
    return module


MOD = load_module()

REPO = "/repo"
TD = REPO + "/.tickets/ai-test"
TPATH = TD + "/ticket.md"

TICKET = """---
id: 'ai-test'
name: 'Test ticket'
status: 'wip'
created: '2026-01-01T00:00:00Z'
parent: null
blocked-on: []
---

# Situation

Prose.

# Tasks

- [ ] Do the thing.
- [ ] Do the other thing.
"""

CLOSED_TICKET = TICKET.replace("status: 'wip'", "status: 'closed'")
OPEN_TICKET = TICKET.replace("status: 'wip'", "status: 'open'")

GOOD_STATE = """# Next
- Run the tests.

# Open

# Cache
- The guard drops at 70. (From: wisp) (Serves: Next)

# Pointers
- /repo/wispy/wispy
"""


class Result:
    def __init__(self, rc, out="", err=""):
        self.rc = rc
        self.out = out
        self.err = err


class FakeFs:
    def __init__(self):
        self.files = {}
        self.dirs = {REPO, TD}

    def exists(self, path):
        return path in self.files or path in self.dirs

    def isdir(self, path):
        return path in self.dirs

    def isfile(self, path):
        return path in self.files

    def read_text(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def _parents(self, path):
        parent = os.path.dirname(path)
        while parent and parent != "/":
            self.dirs.add(parent)
            parent = os.path.dirname(parent)

    def write_text(self, path, text):
        self.files[path] = text
        self._parents(path)

    def append_text(self, path, text):
        self.files[path] = self.files.get(path, "") + text
        self._parents(path)

    def listdir(self, path):
        prefix = path.rstrip("/") + "/"
        names = set()
        for key in list(self.files) + list(self.dirs):
            if key.startswith(prefix):
                rest = key[len(prefix):]
                if rest and "/" not in rest:
                    names.add(rest)
        return sorted(names)

    def mkdir(self, path):
        self.dirs.add(path)

    def remove(self, path):
        self.files.pop(path, None)

    def realpath(self, path):
        return path

    def cwd(self):
        return REPO


class FakeStdin:
    def __init__(self, text, interactive=False):
        self.text = text
        self.interactive = interactive

    def read_text(self):
        return self.text

    def is_interactive(self):
        return self.interactive


class FakeSignal:
    def __init__(self):
        self.seen = False

    def install(self):
        pass

    def interrupted(self):
        return self.seen


class FakeExec:
    """Scripted wisp and git. It also keeps one real wisp.jsonl per run."""

    def __init__(self, fs):
        self.fs = fs
        self.calls = []
        self.streams = []          # [(rc, reply or None)]
        self.ticket_out = TPATH
        self.skills = {}
        self.bs_prompt = ("<wisp>HARNESS</wisp>\n\n"
                          "<agents-md>RULES</agents-md>\n\n"
                          "<skills>CATALOG</skills>\n")
        self.status = ""
        self.ticket_status = ""
        self.heads = ["aaa", "bbb"]
        self.new_fail = ""
        self.on_stream = None

    # -- helpers
    def _value(self, argv, flag):
        return argv[argv.index(flag) + 1]

    def _last_assistant(self, session):
        path = session + "/wisp.jsonl"
        if path not in self.fs.files:
            return None
        text = None
        for line in self.fs.files[path].splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "assistant":
                text = rec.get("content")[0].get("text")
        return text

    # -- output
    def output(self, argv, stdin_text="", cwd=None):
        self.calls.append(("output", tuple(argv), stdin_text))
        if argv[0] == "wisp":
            return self._wisp(argv)
        if argv[0] == "tikit":
            return Result(0, self.ticket_out + ("\n" if self.ticket_out else ""))
        if argv[0] == "git":
            return self._git(argv)
        return Result(127, "", "not found")

    def _wisp(self, argv):
        sub = argv[1]
        if sub == "new":
            if self.new_fail:
                return Result(1, "", self.new_fail)
            name = self._value(argv, "--name")
            path = "/s/" + name
            if path in self.fs.dirs:
                return Result(1, "", "wisp: session dir already exists: %s\n"
                              % path)
            self.fs.mkdir(path)
            self.fs.write_text(path + "/wisp.jsonl", "")
            return Result(0, path + "\n")
        if sub == "build-system-prompt":
            return Result(0, self.bs_prompt)
        if sub == "skill":
            body = self.skills.get(argv[3])
            if body is None:
                return Result(1, "", "wisp: skill not found: %s\n" % argv[3])
            return Result(0, body)
        if sub == "response":
            text = self._last_assistant(self._value(argv, "-d"))
            if text is None:
                return Result(1, "", "wisp: no final assistant message\n")
            return Result(0, text + "\n")
        if sub == "steer":
            return Result(0)
        return Result(1, "", "bad wisp call %s" % (argv,))

    def _git(self, argv):
        args = argv[1:]
        if args == ["rev-parse", "--show-toplevel"]:
            return Result(0, REPO + "\n")
        if args[:2] == ["rev-parse", "HEAD"]:
            return Result(0, (self.heads.pop(0) if self.heads else "zzz")
                          + "\n")
        if args == ["status", "--porcelain"]:
            return Result(0, self.status)
        if args[:2] == ["status", "--porcelain"]:
            return Result(0, self.ticket_status)
        if args[:2] == ["show", "--stat"]:
            return Result(0, " stat line\n")
        return Result(1, "", "bad git call")

    # -- stream
    def stream(self, argv, stdin_text="", to_stdout=True, cwd=None):
        self.calls.append(("stream", tuple(argv), stdin_text, to_stdout))
        rc, reply = self.streams.pop(0) if self.streams else (0, None)
        session = self._value(argv, "-d")
        log = session + "/wisp.jsonl"
        self.fs.append_text(log, json.dumps(
            {"type": "user", "content": stdin_text}) + "\n")
        if reply is not None:
            self.fs.append_text(log, json.dumps(
                {"type": "assistant",
                 "content": [{"type": "text", "text": reply}]}) + "\n")
        if self.on_stream is not None:
            hook, self.on_stream = self.on_stream, None
            hook()
        return Result(rc)

    # -- queries used by the tests
    def stream_calls(self):
        return [c for c in self.calls if c[0] == "stream"]


class Harness:
    def __init__(self, ticket=None, state=None, env=None, stdin="",
                 interactive=False):
        self.fs = FakeFs()
        prompts = os.path.join(os.path.dirname(HERE), "prompts")
        for name in sorted(os.listdir(prompts)):
            path = os.path.join(prompts, name)
            with open(path, encoding="utf-8") as handle:
                self.fs.write_text(path, handle.read())
        self.fs.write_text(TPATH, ticket if ticket is not None else TICKET)
        if state is not None:
            self.fs.write_text(TD + "/STATE.md", state)
        self.exec = FakeExec(self.fs)
        self.out = io.StringIO()
        self.err = io.StringIO()
        self.signals = FakeSignal()
        self.world = MOD.World(MOD.IMPLS)
        self.world.set("fs", self.fs)
        self.world.set("exec", self.exec)
        self.world.set("env", dict({"WISPY_TICKET": TPATH}, **(env or {})))
        self.world.set("stdout", MOD.Stdio(self.out))
        self.world.set("stderr", MOD.Stdio(self.err))
        self.world.set("stdin", FakeStdin(stdin, interactive))
        self.world.set("signal", self.signals)

    def run(self, *argv):
        try:
            argv = list(argv)
            if argv and argv[0] in ("run", "continue", "commit") and not any(
                    arg.startswith("--model") for arg in argv):
                argv += ["--model", "test-model"]
            opts = MOD.parse_args(self.world, argv)
            if opts is None:
                return 0
            return MOD.COMMANDS[opts.command](self.world, opts)
        except MOD.CmdError as exc:
            if exc.message:
                self.err.write(exc.message + "\n")
            return exc.code

    def phase(self):
        path = TD + "/.phase"
        return self.fs.files.get(path, "").strip()

    def add_session(self, seq, assistants=1):
        session = "/s/ai-test-%s" % seq
        self.fs.mkdir(session)
        lines = []
        for index in range(assistants):
            lines.append(json.dumps(
                {"type": "assistant",
                 "content": [{"type": "text", "text": "old %d" % index}]}))
        self.fs.write_text(session + "/wisp.jsonl", "\n".join(lines) + "\n")
        return session

    def errors(self):
        return self.err.getvalue()


class BindingTests(unittest.TestCase):
    def test_path_binding(self):
        harness = Harness()
        ticket = harness.world.get("ticket").open()
        self.assertEqual(ticket.id, "ai-test")
        self.assertEqual(ticket.dir, TD)

    def test_id_binding(self):
        harness = Harness(env={"WISPY_TICKET": "ai-test"})
        ticket = harness.world.get("ticket").open()
        self.assertEqual(ticket.path, TPATH)

    def test_empty_binding_exits_two(self):
        harness = Harness(env={"WISPY_TICKET": ""})
        self.assertEqual(harness.run("run"), 2)

    def test_unset_binding_exits_two(self):
        harness = Harness(env={"WISPY_TICKET": "  "})
        self.assertEqual(harness.run("run"), 2)

    def test_unresolved_id_exits_two(self):
        harness = Harness(env={"WISPY_TICKET": "nope"})
        harness.exec.ticket_out = ""
        self.assertEqual(harness.run("run"), 2)

    def test_path_without_ticket_md_exits_two(self):
        harness = Harness(env={"WISPY_TICKET": TD + "/other.md"})
        self.assertEqual(harness.run("run"), 2)

    def test_positional_argument_is_refused(self):
        harness = Harness()
        self.assertEqual(harness.run("run", "ai-test"), 2)


class RunTests(unittest.TestCase):
    def test_happy_path(self):
        harness = Harness()
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        rc = harness.run("run")
        self.assertEqual(rc, 0)
        self.assertEqual(harness.phase(), "")
        self.assertEqual(harness.fs.files[TD + "/STATE.md"], GOOD_STATE)
        self.assertEqual(harness.fs.files[TD + "/states/001.md"], GOOD_STATE)
        self.assertEqual(harness.fs.files[TD + "/responses/001.md"],
                         "the answer\n")
        self.assertEqual(harness.fs.files[TD + "/sessions.txt"],
                         "/s/ai-test-001\n")
        self.assertNotIn(TD + "/responses/.gitignore", harness.fs.files)
        self.assertEqual(harness.fs.files[TD + "/personas/.gitignore"], "*\n")
        persona = harness.fs.files[TD + "/personas/001.txt"]
        self.assertIn("<wisp>HARNESS</wisp>", persona)
        self.assertIn('<ticket id="ai-test"', persona)
        work, distill = harness.exec.stream_calls()
        self.assertIn("<ticket id=\"ai-test\"", work[2])
        self.assertIn("<state>", work[2])
        self.assertNotIn("<request>", work[2])
        self.assertTrue(work[3])
        self.assertFalse(distill[3])
        self.assertIn("distill stream silenced", harness.errors())

    def test_the_run_rules_reach_the_work_persona(self):
        harness = Harness()
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        persona = harness.fs.files[TD + "/personas/001.txt"]
        self.assertIn("The ticket is the contract", persona)
        self.assertIn("Do not plan a commit", persona)

    def test_request_enters_the_first_session_only(self):
        harness = Harness(stdin="do the thing")
        harness.exec.streams = [(75, "a1"), (0, GOOD_STATE),
                                (0, "a2"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        work1, distill1, work2, distill2 = harness.exec.stream_calls()
        self.assertIn("<request>\ndo the thing\n</request>", work1[2])
        self.assertNotIn("<request>", work2[2])
        self.assertEqual(harness.phase(), "")

    def test_guard_75_loops(self):
        harness = Harness()
        harness.exec.streams = [(75, "a1"), (0, GOOD_STATE),
                                (0, "a2"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertEqual(harness.fs.files[TD + "/.seq"], "2\n")
        self.assertEqual(
            harness.fs.files[TD + "/sessions.txt"],
            "/s/ai-test-001\n/s/ai-test-002\n")
        self.assertEqual(harness.fs.files[TD + "/states/002.md"], GOOD_STATE)
        self.assertIn("<state>", harness.exec.stream_calls()[2][2])

    def test_only_the_work_run_carries_the_guard(self):
        harness = Harness()
        harness.exec.streams = [(75, "a1"), (0, GOOD_STATE),
                                (0, "a2"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        calls = harness.exec.stream_calls()
        self.assertIn("--context-guard", calls[0][1])
        self.assertNotIn("--context-guard", calls[1][1])
        self.assertIn("--context-guard", calls[2][1])
        self.assertNotIn("--context-guard", calls[3][1])

    def test_api_error_exits_one_and_keeps_work(self):
        harness = Harness()
        harness.exec.streams = [(1, None)]
        self.assertEqual(harness.run("run"), 1)
        self.assertEqual(harness.phase(), "work 001 /s/ai-test-001")
        self.assertEqual(len(harness.exec.stream_calls()), 1)
        self.assertIn("API error", harness.errors())

    def test_session_cap_exits_75(self):
        harness = Harness()
        harness.exec.streams = [(75, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run", "--max-sessions", "1"), 75)
        self.assertIn("session cap 1 reached", harness.errors())
        self.assertEqual(len(harness.exec.stream_calls()), 2)

    def test_sigint_exits_130_without_a_distill(self):
        harness = Harness()
        harness.exec.streams = [(130, "the answer")]
        harness.exec.on_stream = lambda: setattr(
            harness.signals, "seen", True)
        self.assertEqual(harness.run("run"), 130)
        self.assertEqual(harness.phase(), "work 001 /s/ai-test-001")
        self.assertEqual(len(harness.exec.stream_calls()), 1)
        self.assertEqual(harness.fs.files[TD + "/responses/001.md"],
                         "the answer\n")
        self.assertIn("Ctrl-c", harness.errors())

    def test_an_open_ticket_is_marked_wip(self):
        harness = Harness(ticket=OPEN_TICKET)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("status: 'wip'", harness.fs.files[TPATH])
        self.assertNotIn("status: 'open'", harness.fs.files[TPATH])
        self.assertIn("open -> wip", harness.errors())
        self.assertIn("status: 'wip'", harness.exec.stream_calls()[0][2])

    def test_a_wip_ticket_is_not_rewritten(self):
        harness = Harness()
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertEqual(harness.fs.files[TPATH], TICKET)
        self.assertNotIn("-> wip", harness.errors())

    def test_a_closed_ticket_reopens_to_wip(self):
        harness = Harness(ticket=CLOSED_TICKET)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("status: 'wip'", harness.fs.files[TPATH])
        self.assertIn("closed -> wip", harness.errors())
        work = harness.exec.stream_calls()[0]
        self.assertTrue(work[3])
        self.assertIn("status: 'wip'", work[2])

    def test_a_closed_ticket_with_a_work_phase_reopens(self):
        harness = Harness(ticket=CLOSED_TICKET)
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        work = harness.exec.stream_calls()[0]
        self.assertTrue(work[3])
        self.assertIn("status: 'wip'", harness.fs.files[TPATH])
        self.assertIn("closed -> wip", harness.errors())
        self.assertEqual(harness.phase(), "")

    def test_a_distill_retry_keeps_a_closed_ticket_closed(self):
        harness = Harness(ticket=CLOSED_TICKET)
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("status: 'closed'", harness.fs.files[TPATH])
        self.assertNotIn("-> wip", harness.errors())

    def test_a_ticket_with_no_status_field_exits_two(self):
        harness = Harness(ticket=TICKET.replace("status: 'wip'\n", ""))
        self.assertEqual(harness.run("run"), 2)
        self.assertIn("no status field", harness.errors())
        self.assertEqual(harness.exec.stream_calls(), [])

    def test_killed_run_with_a_finished_round_distills_then_exits(self):
        harness = Harness()
        harness.exec.streams = [(143, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 143)
        self.assertEqual(harness.phase(), "")
        self.assertEqual(harness.fs.files[TD + "/STATE.md"], GOOD_STATE)

    def test_killed_run_with_no_round_abandons(self):
        harness = Harness()
        harness.exec.streams = [(137, None)]
        self.assertEqual(harness.run("run"), 137)
        self.assertEqual(harness.phase(), "")
        self.assertEqual(harness.fs.files[TD + "/sessions.txt"],
                         "/s/ai-test-001\n")


class DistillTests(unittest.TestCase):
    def test_distill_stop_retry(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertEqual(harness.phase(), "")
        self.assertEqual(harness.fs.files[TD + "/STATE.md"], GOOD_STATE)

    def test_distill_loop_retry_starts_a_session(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.seq", "1\n")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s LOOP\n" % session)
        harness.exec.streams = [(0, GOOD_STATE), (0, "a2"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertEqual(harness.phase(), "")
        self.assertEqual(harness.fs.files[TD + "/.seq"], "2\n")

    def test_a_distill_retry_carries_no_guard(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(0, GOOD_STATE)]
        self.assertEqual(harness.run("continue"), 0)
        self.assertNotIn("--context-guard", harness.exec.stream_calls()[0][1])

    def test_distill_with_no_new_assistant_keeps_the_marker(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(0, None)]
        self.assertEqual(harness.run("run"), 1)
        self.assertIn("gave no output", harness.errors())
        self.assertEqual(harness.phase(), "distill 001 %s STOP" % session)

    def test_distill_error_keeps_the_marker(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(1, None)]
        self.assertEqual(harness.run("run"), 1)
        self.assertEqual(harness.phase(), "distill 001 %s STOP" % session)
        self.assertIn("retries the distill", harness.errors())

    def test_a_code_fence_is_stripped(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"),
                                (0, "```markdown\n" + GOOD_STATE + "```")]
        self.assertEqual(harness.run("run"), 0)
        self.assertEqual(harness.fs.files[TD + "/STATE.md"], GOOD_STATE)

    def test_non_empty_open_is_noted(self):
        harness = Harness()
        state = ("# Next\n- a\n\n# Open\n- Q: one or two?\n\n"
                 "# Cache\n\n# Pointers\n")
        harness.exec.streams = [(0, "a1"), (0, state)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("1 open question(s)", harness.errors())

    def test_over_cap_is_noted(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run", "--cap", "3"), 0)
        self.assertIn("the cap is 3", harness.errors())

    def test_cap_flag_reaches_the_prompt(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run", "--cap", "42"), 0)
        self.assertIn("The cap is 42 non-empty lines",
                      harness.exec.stream_calls()[1][2])
        self.assertNotIn("@@CAP@@", harness.exec.stream_calls()[1][2])

    def test_cache_line_without_a_key_is_noted(self):
        harness = Harness()
        state = ("# Next\n- a\n\n# Open\n\n"
                 "# Cache\n- a bare fact\n\n# Pointers\n")
        harness.exec.streams = [(0, "a1"), (0, state)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("no (Serves: ...) key", harness.errors())

    def test_cache_line_whose_target_is_gone_is_noted(self):
        harness = Harness()
        state = ("# Next\n\n# Open\n\n# Cache\n"
                 "- a fact. (From: a, b) (Serves: Next)\n\n# Pointers\n")
        harness.exec.streams = [(0, "a1"), (0, state)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("Next is empty", harness.errors())

    def test_cache_line_with_a_gone_task_is_noted(self):
        harness = Harness()
        state = ("# Next\n- a\n\n# Open\n\n# Cache\n"
                 "- a fact. (From: a, b) (Serves: task 9)\n\n# Pointers\n")
        harness.exec.streams = [(0, "a1"), (0, state)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("has 2 tasks", harness.errors())

    def test_a_percent_guard_is_accepted(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run", "--guard", "70%"), 0)
        self.assertIn("--context-guard", harness.exec.stream_calls()[0][1])
        self.assertEqual(harness.exec.stream_calls()[0][1][-1], "70%")

    def test_a_missing_section_is_noted(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"), (0, "# Next\n- a\n")]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("no cache section", harness.errors())

    def test_the_distill_prompt_carries_the_waiting_line_rule(self):
        harness = Harness()
        harness.exec.streams = [(0, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        prompt = harness.exec.stream_calls()[1][2]
        self.assertIn("moves only on a user answer", prompt)
        self.assertIn("(Serves: Next)", prompt)
        self.assertIn("The mode is STOP", prompt)
        self.assertIn("distill stream", harness.errors())

    def test_the_loop_mode_is_in_the_prompt(self):
        harness = Harness()
        harness.exec.streams = [(75, "a1"), (0, GOOD_STATE),
                                (0, "a2"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("The mode is LOOP",
                      harness.exec.stream_calls()[1][2])


class ContinueTests(unittest.TestCase):
    def test_no_marker_exits_two(self):
        harness = Harness()
        self.assertEqual(harness.run("continue"), 2)
        self.assertIn("no open session", harness.errors())

    def test_empty_stdin_resumes_with_wisp_continue(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("continue"), 0)
        first = harness.exec.stream_calls()[0]
        self.assertEqual(first[1][1], "continue")
        self.assertEqual(first[2], "")

    def test_a_continue_reopens_a_closed_ticket(self):
        harness = Harness(ticket=CLOSED_TICKET)
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("continue"), 0)
        self.assertIn("status: 'wip'", harness.fs.files[TPATH])

    def test_text_on_stdin_resumes_with_wisp_run(self):
        harness = Harness(stdin="next step")
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        harness.exec.streams = [(0, "the answer"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("continue"), 0)
        first = harness.exec.stream_calls()[0]
        self.assertEqual(first[1][1], "run")
        self.assertIn("<request>\nnext step\n</request>", first[2])

    def test_a_commit_marker_exits_two(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "commit c01 %s\n" % session)
        self.assertEqual(harness.run("continue"), 2)

    def test_a_finished_segment_names_the_repair(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        harness.exec.streams = [(1, None)]
        self.assertEqual(harness.run("continue"), 1)
        self.assertIn("already finished", harness.errors())

    def test_skills_on_a_resume_exits_two(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        self.assertEqual(harness.run("continue", "--skills", "a"), 2)


class SteerTests(unittest.TestCase):
    def test_no_marker_exits_two(self):
        harness = Harness(stdin="hello")
        self.assertEqual(harness.run("steer"), 2)

    def test_empty_stdin_exits_two(self):
        harness = Harness(stdin="  \n")
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        self.assertEqual(harness.run("steer"), 2)

    def test_it_steers_the_session_in_the_marker(self):
        harness = Harness(stdin="use the second option")
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        self.assertEqual(harness.run("steer"), 0)
        call = [c for c in harness.exec.calls if c[1][:2] == ("wisp", "steer")]
        self.assertEqual(call[0][1][3], session)
        self.assertEqual(call[0][2], "use the second option")

    def test_a_commit_marker_exits_two(self):
        harness = Harness(stdin="hello")
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "commit c01 %s\n" % session)
        self.assertEqual(harness.run("steer"), 2)


class SkillsTests(unittest.TestCase):
    def test_skills_reach_the_persona(self):
        harness = Harness()
        harness.exec.skills = {"alpha": '<skill name="alpha">BODY</skill>\n'}
        harness.exec.streams = [(0, "a1"), (0, GOOD_STATE)]
        self.assertEqual(harness.run("run", "--skills", "alpha"), 0)
        persona = harness.fs.files[TD + "/personas/001.txt"]
        self.assertIn("<skills>CATALOG</skills>", persona)
        self.assertIn('<skill name="alpha">BODY</skill>', persona)
        self.assertEqual(harness.fs.files[TD + "/skills/001.txt"], "alpha\n")

    def test_an_unknown_skill_exits_two(self):
        harness = Harness()
        self.assertEqual(harness.run("run", "--skills", "nope"), 2)
        self.assertIn("no skill named nope", harness.errors())
        self.assertEqual(harness.exec.stream_calls(), [])

    def test_skills_are_refused_on_steer(self):
        harness = Harness(stdin="hello")
        self.assertEqual(harness.run("steer", "--skills", "a"), 2)


class CommitTests(unittest.TestCase):
    def test_a_work_marker_exits_two(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "work 001 %s\n" % session)
        self.assertEqual(harness.run("commit"), 2)
        self.assertIn("unfinished run", harness.errors())

    def test_a_clean_tree_exits_zero_without_a_session(self):
        harness = Harness()
        harness.exec.status = ""
        self.assertEqual(harness.run("commit"), 0)
        self.assertEqual(harness.exec.stream_calls(), [])
        self.assertIn("nothing to commit", harness.errors())

    def test_the_commit_writes_the_wrapper_gitignore(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        text = harness.fs.files[TD + "/.gitignore"]
        for item in (".phase", ".seq", "skills/", "personas/"):
            self.assertIn(item + "\n", text)
        self.assertNotIn("responses/", text)
        self.assertIn(".gitignore", harness.exec.stream_calls()[0][2])

    def test_the_commit_drops_a_legacy_response_ignore(self):
        harness = Harness()
        harness.fs.write_text(TD + "/.gitignore", ".phase\nresponses/\n")
        harness.fs.write_text(TD + "/responses/.gitignore", "*\n")
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        text = harness.fs.files[TD + "/.gitignore"]
        self.assertNotIn("responses/", text)
        self.assertIn(".phase\n", text)
        self.assertNotIn(TD + "/responses/.gitignore", harness.fs.files)

    def test_a_response_is_record_after_the_commit(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.ticket_status = "?? .tickets/ai-test/responses/001.md\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 1)
        self.assertIn("uncommitted record", harness.errors())
        self.assertIn("responses/001.md", harness.errors())

    def test_a_lone_response_starts_the_commit(self):
        harness = Harness()
        harness.exec.status = "?? .tickets/ai-test/responses/001.md\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        self.assertEqual(len(harness.exec.stream_calls()), 1)

    def test_the_gitignore_keeps_an_existing_line(self):
        harness = Harness()
        harness.fs.write_text(TD + "/.gitignore", "build/\n.phase\n")
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        text = harness.fs.files[TD + "/.gitignore"]
        self.assertTrue(text.startswith("build/\n.phase\n"))
        self.assertEqual(text.count(".phase\n"), 1)
        self.assertIn("skills/\n", text)

    def test_wrapper_state_does_not_block_the_clean_check(self):
        harness = Harness()
        harness.exec.status = ("?? .tickets/ai-test/.gitignore\n"
                               "?? .tickets/ai-test/.seq\n"
                               "?? .tickets/ai-test/skills/001.txt\n")
        self.assertEqual(harness.run("commit"), 0)
        self.assertEqual(harness.exec.stream_calls(), [])
        self.assertIn("nothing to commit", harness.errors())

    def test_wrapper_state_is_not_record_after_the_commit(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.ticket_status = ("?? .tickets/ai-test/.phase\n"
                                      " M .tickets/ai-test/.seq\n"
                                      "?? .tickets/ai-test/skills/c01.txt\n")
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)

    def test_a_dirty_tree_makes_one_commit(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        calls = harness.exec.stream_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("wip(ai-test): Test ticket", calls[0][2])
        self.assertEqual(harness.phase(), "")
        self.assertIn("/s/ai-test-c01\n",
                      harness.fs.files[TD + "/sessions.txt"])

    def test_the_run_rules_stay_out_of_the_commit_persona(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        persona = harness.fs.files[TD + "/personas/c01.txt"]
        self.assertIn('<ticket id="ai-test"', persona)
        self.assertNotIn("Do not plan a commit", persona)

    def test_a_commit_that_moves_no_head_exits_one(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.heads = ["aaa", "aaa"]
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 1)
        self.assertIn("made no commit", harness.errors())

    def test_a_dirty_ticket_dir_after_the_commit_exits_one(self):
        harness = Harness()
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.ticket_status = " M .tickets/ai-test/STATE.md\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 1)
        self.assertIn("holds uncommitted record", harness.errors())

    def test_a_closed_ticket_uses_the_closed_subject(self):
        harness = Harness(ticket=CLOSED_TICKET)
        harness.exec.status = " M wispy/wispy\n"
        harness.exec.streams = [(0, "sealed")]
        self.assertEqual(harness.run("commit"), 0)
        self.assertIn("closed(ai-test): Test ticket",
                      harness.exec.stream_calls()[0][2])

    def test_a_commit_marker_is_retried(self):
        harness = Harness()
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "commit c01 %s\n" % session)
        harness.exec.status = ""
        self.assertEqual(harness.run("commit"), 0)
        self.assertEqual(harness.phase(), "")


class CommitSubjectTests(unittest.TestCase):
    def subject(self, status, name="Test ticket"):
        return MOD.commit_subject(MOD.Ticket(
            id="ai-test", name=name, status=status, path=TPATH, dir=TD,
            text=TICKET))

    def test_a_wip_ticket_uses_wip(self):
        self.assertEqual(self.subject("wip"), "wip(ai-test): Test ticket")

    def test_a_closed_ticket_uses_closed(self):
        self.assertEqual(self.subject("closed"),
                         "closed(ai-test): Test ticket")

    def test_any_other_status_names_itself(self):
        self.assertEqual(self.subject("open"), "open(ai-test): Test ticket")

    def test_an_empty_status_falls_back_to_work(self):
        self.assertEqual(self.subject(""), "work(ai-test): Test ticket")

    def test_a_missing_name_shows_a_placeholder(self):
        self.assertEqual(self.subject("wip", ""), "wip(ai-test): <name>")


class ResponseTests(unittest.TestCase):
    def test_it_prints_the_newest_by_number(self):
        harness = Harness()
        harness.fs.write_text(TD + "/responses/002.md", "two\n")
        harness.fs.write_text(TD + "/responses/010.md", "ten\n")
        self.assertEqual(harness.run("response"), 0)
        self.assertEqual(harness.out.getvalue(), "ten\n")

    def test_no_response_exits_two(self):
        harness = Harness()
        self.assertEqual(harness.run("response"), 2)


class PhaseTests(unittest.TestCase):
    def test_decide_after_work(self):
        self.assertEqual(MOD.decide_after_work(0, False, True),
                         ("stop", 0))
        self.assertEqual(MOD.decide_after_work(75, False, True),
                         ("loop", 0))
        self.assertEqual(MOD.decide_after_work(1, False, True),
                         ("api", 0))
        self.assertEqual(MOD.decide_after_work(130, True, True),
                         ("sigint", 0))
        self.assertEqual(MOD.decide_after_work(2, False, True),
                         ("stop", 2))
        self.assertEqual(MOD.decide_after_work(2, False, False),
                         ("abandon", 2))

    def test_run_on_a_distill_marker_drops_the_request(self):
        harness = Harness(stdin="ignored")
        session = harness.add_session("001")
        harness.fs.write_text(TD + "/.phase", "distill 001 %s STOP\n" % session)
        harness.exec.streams = [(0, GOOD_STATE)]
        self.assertEqual(harness.run("run"), 0)
        self.assertIn("the request on stdin is not used", harness.errors())
        self.assertNotIn("ignored", harness.exec.stream_calls()[0][2])

    def test_a_bad_marker_exits_two(self):
        harness = Harness()
        harness.fs.write_text(TD + "/.phase", "frame 001 /s/x\n")
        self.assertEqual(harness.run("run"), 2)

    def test_a_gone_session_dir_exits_two(self):
        harness = Harness()
        harness.fs.write_text(TD + "/.phase", "work 001 /s/gone\n")
        self.assertEqual(harness.run("run"), 2)


class PromptFileTests(unittest.TestCase):
    def read(self, name):
        base = os.path.join(os.path.dirname(HERE), "prompts")
        with open(os.path.join(base, name), encoding="utf-8") as handle:
            return handle.read()

    def test_the_rule_files_exist(self):
        base = os.path.join(os.path.dirname(HERE), "prompts")
        for name in ("run-rules.md", "distill-rules.md", "commit-rules.md"):
            self.assertTrue(os.path.isfile(os.path.join(base, name)))

    def test_the_wrapper_writes_the_state_file(self):
        self.assertIn("The wrapper writes the file from your",
                      self.read("distill-rules.md"))

    def test_the_gaps_section_does_not_count_against_the_cap(self):
        self.assertIn("`## Gaps` does not count against this cap",
                      self.read("distill-rules.md"))

    def test_a_question_has_one_home_per_mode(self):
        text = self.read("distill-rules.md")
        self.assertIn("It does not go to ticket `Gaps`", text)
        self.assertIn("It does not go in the", text)

    def test_no_commit_hash_goes_into_the_state(self):
        self.assertIn("Record no commit", self.read("distill-rules.md"))

    def test_the_distill_names_no_commit(self):
        text = self.read("distill-rules.md")
        self.assertIn("Do not commit in this turn.", text)
        self.assertNotIn("The user types `wispy commit` after this run",
                         text)

    def test_the_run_rules_do_not_promise_a_commit(self):
        text = self.read("run-rules.md")
        self.assertIn("If the user did not explicitly request you to",
                      text)
        self.assertNotIn("The user types `wispy commit` after this run",
                         text)

    def test_the_commit_names_the_two_sets(self):
        text = self.read("commit-rules.md")
        self.assertIn("Record: `ticket.md`, `STATE.md`, `states/`,"
                      " `responses/`, and\n  `sessions.txt`", text)
        self.assertIn("Wrapper state: `.phase`, `.seq`, `skills/`, and"
                      " `personas/`", text)
        self.assertIn("Do not stage, commit,", text)
        self.assertIn("The commit\nturn writes no response", text)

    def test_the_commit_runs_no_check(self):
        text = self.read("commit-rules.md")
        self.assertIn("This is a seal, not a review.", text)
        self.assertIn("Run no check.", text)
        self.assertIn("Do not run a test, lint, type check, build, or any\n"
                      "other verification command.", text)
        self.assertIn("Run only the git commands and the file reads", text)

    def test_the_commit_bounds_the_transcript_read(self):
        text = self.read("commit-rules.md")
        self.assertIn("Do not read a `wisp.jsonl` whole.", text)
        self.assertIn("`states/NNN.md` and `responses/NNN.md`", text)
        self.assertNotIn("every session dir that `sessions.txt` names",
                         text)

    def test_the_commit_amends_only_on_request(self):
        text = self.read("commit-rules.md")
        self.assertIn("If the user did not ask you to amend", text)
        self.assertIn("amend the HEAD commit", text)
        self.assertIn("Do not rebase or reset.", text)
        self.assertNotIn("Do not amend, rebase, or reset.", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
