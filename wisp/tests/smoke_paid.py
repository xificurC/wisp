"""Paid smoke test for one provider through a live LLM endpoint.

Runs the real wire path - build_request, sse_stream on urllib, TurnAcc
- against the endpoint that the environment names. NOT part of the
unittest discovery (name does not match test*.py); run by hand:

    python3 tests/smoke_paid.py anthropic
    python3 tests/smoke_paid.py responses
    python3 tests/smoke_paid.py chat

The test reads four variables from the environment:

    WISP_LLM_URL            the full request URL for that shape
    WISP_LLM_API_KEY        the key for that URL
    WISP_SMOKE_MODEL        the model id to call
    WISP_SMOKE_FALLBACK_MODEL   optional second model, tried when the
                                first one fails

A per-provider override also works: WISP_SMOKE_MODEL_ANTHROPIC,
WISP_SMOKE_MODEL_RESPONSES, WISP_SMOKE_MODEL_CHAT. Each shape has its
own path, so run one shape per URL; wisp appends nothing to the URL.

Four small turns: prefix plant, cache-read check, tool call (with
thinking on anthropic), signature/encrypted replay. Asserts cached
tokens above zero from turn 2 on, a tool-call block on turn 3, and no
signature failure on turn 4. Expected cost: under one cent.

With --attach, one vision turn instead: a 64x64 solid red PNG goes to
the model as an inline image attachment, and the answer must name
the color. One turn, one tiny image, all three providers:

    python3 tests/smoke_paid.py anthropic --attach
    python3 tests/smoke_paid.py responses --attach
    python3 tests/smoke_paid.py chat --attach
"""

import base64
import importlib.machinery
import importlib.util
import json
import os
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load_wisp():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "wisp")
    loader = importlib.machinery.SourceFileLoader("wisp", path)
    spec = importlib.util.spec_from_loader("wisp", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


PROVIDERS = ("anthropic", "responses", "chat")

API_OF = {"anthropic": "anthropic", "responses": "openai-responses",
          "chat": "openai-chat"}


def model_from_env(provider: str) -> str:
    """The model id: the per-provider override first, then the shared one."""
    return (os.environ.get("WISP_SMOKE_MODEL_" + provider.upper())
            or os.environ.get("WISP_SMOKE_MODEL", ""))


def fallback_model() -> str:
    return os.environ.get("WISP_SMOKE_FALLBACK_MODEL", "")


def _red_png() -> bytes:
    """64x64 solid red PNG, stdlib only. An 8x8 image proved too small
    for some vision preprocessors, which answered black."""
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * 64 for _ in range(64))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

FILLER = ("The wisp agent keeps one session file in plain JSON lines. "
          "Every record lands in arrival order; the renderer walks the "
          "same file. " * 95)  # ~2500 tokens, over the 2048-token
                               # cache minimum of the larger models. A
                               # smaller minimum is fine: the prefix stays
                               # cacheable.


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else ""
    reasoning_from_start = "--reasoning" in sys.argv
    attach = "--attach" in sys.argv
    if provider not in PROVIDERS:
        print("usage: smoke_paid.py anthropic|responses|chat"
              " [--attach] [--reasoning]")
        return 2
    model = model_from_env(provider)
    if not model:
        print("error: set WISP_SMOKE_MODEL or WISP_SMOKE_MODEL_%s"
              % provider.upper())
        return 2
    if not os.environ.get("WISP_LLM_URL") or not os.environ.get(
            "WISP_LLM_API_KEY"):
        print("error: set WISP_LLM_URL and WISP_LLM_API_KEY")
        return 2
    wisp = _load_wisp()
    env = dict(os.environ)
    env["WISP_LLM_API"] = API_OF[provider]
    if provider == "anthropic":
        env["WISP_LLM_MAX_TOKENS"] = "4096"

    if attach:
        return attach_smoke(wisp, env, provider, model)

    results = {}

    def attempt(model, reasoning_from_start=False):
        world = wisp.World(wisp.IMPLS)
        world.set("env", env)
        world.set("sessiondir", results["dir"])
        world.set("model", model)
        world.set("thinking", "high" if reasoning_from_start else None)
        records = [
            {"type": "system", "content": "You are terse. Reply in as "
             "few words as possible."},
            {"type": "user", "content": FILLER + "\nReply with exactly: ok"},
        ]
        out = []
        t1 = world.get("llm").turn(records)
        out.append(("t1", t1))
        records = records + [t1["assistant"],
                             {"type": "user", "content": "Say hi in one word."}]
        t2 = world.get("llm").turn(records)
        out.append(("t2", t2))
        world.set("thinking", "high")
        records = records + [t2["assistant"],
                             {"type": "user", "content":
                              "Call the bash tool with command 'echo hi', "
                              "then reply done."}]
        t3 = world.get("llm").turn(records)
        out.append(("t3", t3))
        # the run loop always appends the tool results before the next
        # turn; anthropic rejects a tool_use without its tool_result
        tools_out = []
        for b in t3["assistant"]["output"]:
            if b["type"] == "tool_call":
                tools_out.append({"type": "tool", "call_id": b["id"],
                                  "name": b["name"],
                                  "content": "hi\n", "exit": 0})
        records = records + [t3["assistant"]] + tools_out + [
                             {"type": "user", "content":
                              "Reply with exactly: done"}]
        t4 = world.get("llm").turn(records)
        out.append(("t4", t4))
        return out

    with tempfile.TemporaryDirectory() as td:
        results["dir"] = td
        try:
            turns = attempt(model, reasoning_from_start)
        except (SystemExit, wisp.HttpError):
            spare = fallback_model()
            if not spare or model == spare:
                raise
            print("model %s failed, falling back to %s" % (model, spare))
            model = spare
            turns = attempt(model, reasoning_from_start)

        for name, t in turns:
            blocks = [(b["type"], bool(b.get("signature")),
                       bool(b.get("encrypted_content")))
                      for b in t["assistant"]["output"]]
            print(name, "finish=%s cached=%s blocks=%s"
                  % (t["finish_reason"], t["cached_tokens"], blocks))

        t2, t3, t4 = turns[1][1], turns[2][1], turns[3][1]
        ok = True
        if not t2["cached_tokens"]:
            print("FAIL: turn 2 cached_tokens is 0 - no cache hit")
            ok = False
        if not any(b["type"] == "tool_call"
                   for b in t3["assistant"]["output"]):
            print("FAIL: turn 3 has no tool_call block")
            ok = False
        if not t4["cached_tokens"]:
            print("FAIL: turn 4 cached_tokens is 0 - no cache hit")
            ok = False
        print("SMOKE %s: %s" % (provider, "PASS" if ok else "FAIL"))
        return 0 if ok else 1


def attach_smoke(wisp, env, provider, model):
    """One vision turn: the model must name the red PNG's color."""
    world = wisp.World(wisp.IMPLS)
    world.set("env", env)
    world.set("sessiondir", tempfile.mkdtemp(prefix="wisp-smoke-"))
    world.set("model", model)
    world.set("thinking", None)
    records = [
        {"type": "system", "content": "You are terse."},
        {"type": "user", "content":
         "What color is this image? Answer directly, do not use any "
         "tool. Reply with one word.",
         "attachments": [
             {"name": "red.png", "media_type": "image/png",
              "data": base64.b64encode(_red_png()).decode("ascii")}]},
    ]
    try:
        t = world.get("llm").turn(records)
    except (SystemExit, wisp.HttpError):
        spare = fallback_model()
        if not spare or model == spare:
            raise
        print("model %s failed, falling back to %s" % (model, spare))
        world.set("model", spare)
        t = world.get("llm").turn(records)
    text = "".join(b.get("text", "")
                   for b in t["assistant"].get("output") or []
                   if b.get("type") == "text").strip().lower()
    print("attach %s: answer=%r finish=%s"
          % (provider, text, t["finish_reason"]))
    ok = "red" in text
    print("SMOKE %s --attach: %s" % (provider, "PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
