"""Unit tests for the SUBAGENTS laws: the invariant
list, the recipe forms, the help mandate, and top-level wisp new
without --parent.

The extensionless wisp module imports by path, so the package stays
stdlib only."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
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
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LAWS = [
    "This block carries the subagent laws.",
    "A session with no SUBAGENTS block in its system prompt must not"
    " start children.",
    "It must ask the operator to rebuild its prompt with --wisp.",
    "The parent law: give every child --parent with your session dir.",
    "A child without --parent is an orphan.",
    '"wisp ls --tree" and "wisp grep --tree" cannot see an orphan.',
    'The stream law: send child stdout to "$CHILD/wisp.stream".',
    '"wisp render-live" follows this exact path.',
    "A stream at any other path breaks that tool.",
    "The stream never goes into your tool result.",
    'Read the answer with "wisp response".',
    "Delete the stream after the read.",
    "The stream is temporary data. wisp.jsonl is the record of truth.",
    "The home rule: put every child artifact in the child session dir.",
    "These artifacts are the prompt file, the stream, and captured"
    " response text.",
    "Do not use /tmp.",
    "The symbol map: in the parent recipe, $CHILD names the child run"
    " dir.",
    "In the child session itself, WISP_SESSION_DIR names that same dir.",
    "The shape is open; the invariants are not.",
    "Keep all invariants in each variant of the recipe.",
]

INVARIANTS = """The invariants:
- --parent on every "wisp new" for a child.
- -d on every call.
- Child stdout to "$CHILD/wisp.stream".
- "wisp response -d" for the answer.
- Delete the stream after the read.
- Child artifacts in the child session dir.
- Never export WISP_SESSION_DIR.
"""


def _flat(text):
    return " ".join(text.split())


class SubagentLawsTest(unittest.TestCase):
    """Pins the SUBAGENTS text and the help text (A1, A2, A3)."""

    def test_law_sentences(self):
        flat = _flat(wisp.subagents_block())
        for sentence in LAWS:
            self.assertIn(sentence, flat)

    def test_invariant_list(self):
        self.assertIn(INVARIANTS, wisp.subagents_block())

    def test_recipe_forms(self):
        block = wisp.subagents_block()
        self.assertEqual(3, block.count('rm "$CHILD/wisp.stream"'))
        self.assertEqual(3, block.count(
            'wisp response -d "$CHILD"\n  rm "$CHILD/wisp.stream"'))
        self.assertIn('wisp run -d "$CHILD" --context-guard 70%'
                      ' < "$CHILD/prompt.txt"'
                      ' > "$CHILD/wisp.stream"', block)
        self.assertNotIn("< prompt.txt", block)

    def test_help_mandate(self):
        flat = _flat(wisp.command_help_text("new"))
        self.assertIn("give it to every child session", flat)
        self.assertIn("a child without --parent is an orphan", flat)
        self.assertIn("wisp ls --tree and wisp grep --tree cannot see"
                      " an orphan", flat)

    def test_docstring_mandate(self):
        flat = _flat(wisp.__doc__)
        self.assertIn("[--parent DIR] # child sessions: give it"
                      " always", flat)
        self.assertIn("Give --parent DIR to every child session.", flat)
        self.assertIn("`wisp ls --tree` and `wisp grep --tree` cannot"
                      " see an orphan.", flat)
        self.assertNotIn("[--parent DIR])", wisp.__doc__)


class TopLevelNewTest(unittest.TestCase):
    """A5: wisp new without --parent makes a top-level session."""

    def test_new_without_parent(self):
        with tempfile.TemporaryDirectory() as root:
            env = dict(os.environ, WISP_SESSIONS_ROOT=root)
            run = subprocess.run(
                [os.path.join(REPO, "wisp"), "new", "--name",
                 "top-no-parent", "-m", "test-model"],
                env=env, capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stderr)
            path = run.stdout.strip()
            self.assertEqual(os.path.join(root, "top-no-parent"), path)
            self.assertTrue(os.path.exists(os.path.join(path,
                                                        "wisp.jsonl")))
            with open(os.path.join(path, "wisp.run.json")) as handle:
                self.assertIsNone(json.load(handle).get("parent"))


if __name__ == "__main__":
    unittest.main()
