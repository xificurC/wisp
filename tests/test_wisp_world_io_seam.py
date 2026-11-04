#!/usr/bin/env python3
"""World IO seam: a fake fs and env drive wisp skill ls and skill
read with no real disk access; any IO outside /fake raises."""
import importlib.machinery
import importlib.util
import os

WISP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "wisp", "wisp")
_loader = importlib.machinery.SourceFileLoader("wisp", WISP)
_spec = importlib.util.spec_from_loader("wisp", _loader)
wisp = importlib.util.module_from_spec(_spec)
_loader.exec_module(wisp)

DIRS = {"/fake", "/fake/proj", "/fake/proj/.agents/skills",
        "/fake/proj/.agents/skills/proj-skill",
        "/fake/home/.agents/skills", "/fake/home/.agents/skills/home-skill",
        "/fake/xdg/skills"}
FILES = {
    "/fake/proj/.agents/skills/proj-skill/SKILL.md":
        "---\nname: proj-skill\ndescription: p\n---\nBody p.\n",
    "/fake/home/.agents/skills/home-skill/SKILL.md":
        "---\nname: home-skill\ndescription: h\n---\nBody h.\n",
}


class FakeFs:
    """Answers only for /fake paths; anything else is a direct-disk hit."""

    def _check(self, path):
        if not path.startswith("/fake"):
            raise AssertionError("direct IO outside the fake tree: %s" % path)

    def cwd(self):
        return "/fake/proj"

    def listdir(self, path):
        self._check(path)
        return sorted(p for p in DIRS | FILES.keys() if os.path.dirname(p) == path)

    def isdir(self, path):
        self._check(path)
        return path in DIRS

    def isfile(self, path):
        self._check(path)
        return path in FILES

    def realpath(self, path):
        self._check(path)
        return path

    def read_text(self, path):
        self._check(path)
        return FILES[path]


class FakeExec:
    def output(self, argv):
        return 0, "/fake/proj\n"


class Capture:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


def fake_world():
    return wisp.World({
        "stdout": lambda w: Capture(),
        "stderr": lambda w: Capture(),
        "env": lambda w: {"HOME": "/fake/home"},
        "fs": lambda w: FakeFs(),
        "exec": lambda w: FakeExec(),
    })


world = fake_world()
_cmd, opts = wisp.parse_args(world, ["skill", "ls"])
wisp.skill_command(world, opts)
want = ["home-skill: h (/fake/home/.agents/skills/home-skill/SKILL.md)",
        "proj-skill: p (/fake/proj/.agents/skills/proj-skill/SKILL.md)"]
assert world.get("stdout").text.splitlines() == want, world.get("stdout").text
assert not world.get("stderr").text, world.get("stderr").text

world = fake_world()
_cmd, opts = wisp.parse_args(world, ["skill", "read", "proj-skill"])
wisp.skill_command(world, opts)
assert world.get("stdout").text == (
    '<skill name="proj-skill" '
    'location="/fake/proj/.agents/skills/proj-skill/SKILL.md">\n'
    "References are relative to /fake/proj/.agents/skills/proj-skill.\n\n"
    "Body p.\n</skill>\n"), world.get("stdout").text

print("PASS: test_wisp_world_io_seam")
