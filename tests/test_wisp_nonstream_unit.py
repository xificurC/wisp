#!/usr/bin/env python3
"""Unit tests for the non-stream WISP_LLM_STREAM=false path:
stream_enabled_of's truth table, the body gate, chat_chunk_of's
mapping, TurnAcc over one whole reply, and the provider gate."""
import importlib.machinery
import importlib.util
import os

WISP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "wisp", "wisp")
_loader = importlib.machinery.SourceFileLoader("wisp", WISP)
_spec = importlib.util.spec_from_loader("wisp", _loader)
wisp = importlib.util.module_from_spec(_spec)
_loader.exec_module(wisp)


class Capture:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


def world_of(env, **extra):
    registry = {"env": lambda w: env,
                "stderr": lambda w: Capture(),
                "stdout": lambda w: Capture()}
    registry.update(extra)
    return wisp.World(registry)


def chat_world(env):
    return world_of(env, model=lambda w: "m", thinking=lambda w: "")


# --- stream_enabled_of truth table ------------------------------------------

for env in ({}, {"WISP_LLM_STREAM": ""}, {"WISP_LLM_STREAM": "   "}):
    assert wisp.stream_enabled_of(world_of(env)) is True, env

for raw in ("false", "0", "no", "off", "FALSE", " Off "):
    assert wisp.stream_enabled_of(
        world_of({"WISP_LLM_STREAM": raw})) is False, raw

bad = world_of({"WISP_LLM_STREAM": "maybe"})
try:
    wisp.stream_enabled_of(bad)
except SystemExit as exc:
    assert exc.code == 1
else:
    raise AssertionError("an unknown WISP_LLM_STREAM must fail")
assert bad.get("stderr").text == (
    "wisp: unknown WISP_LLM_STREAM maybe (leave it unset for a stream,"
    " or set false, 0, no or off)\n"), bad.get("stderr").text

# --- body gate ---------------------------------------------------------------

off = wisp.body_of_chat(chat_world({"WISP_LLM_STREAM": "false"}), [])
assert list(off) == ["model", "messages", "tools", "stream"], list(off)
assert off["stream"] is False
assert "stream_options" not in off

on = wisp.body_of_chat(chat_world({}), [])
assert list(on) == ["model", "messages", "tools", "stream",
                    "stream_options"], list(on)
assert on["stream"] is True
assert on["stream_options"] == {"include_usage": True}

# --- chat_chunk_of -----------------------------------------------------------

USAGE = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18,
         "prompt_tokens_details": {"cached_tokens": 3}}
PAYLOAD = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "the whole answer",
            "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "bash",
                              "arguments": '{"command": "echo one"}'}},
                {"id": "call_2", "type": "function",
                 "function": {"name": "bash",
                              "arguments": '{"command": "echo two"}'}},
            ],
        },
        "finish_reason": "tool_calls",
    }],
    "usage": USAGE,
}

for payload in ([], {}, {"choices": []}, {"choices": "nope"}):
    assert wisp.chat_chunk_of(payload) is None, payload

chunk = wisp.chat_chunk_of(PAYLOAD)
choice = chunk["choices"][0]
delta = choice["delta"]
assert choice["finish_reason"] == "tool_calls", choice
assert chunk["usage"] is USAGE
assert delta["content"] == "the whole answer", delta
assert [tc["index"] for tc in delta["tool_calls"]] == [0, 1], delta
assert delta["tool_calls"][0] == {
    "index": 0, "id": "call_1", "type": "function",
    "function": {"name": "bash", "arguments": '{"command": "echo one"}'}}
assert delta["tool_calls"][1]["id"] == "call_2"
assert delta["tool_calls"][1]["function"]["arguments"] == (
    '{"command": "echo two"}')

# A message with no arguments field still maps a function with empty
# arguments.
assert wisp.chat_chunk_of({
    "choices": [{"message": {"tool_calls": [
        {"id": "c", "function": {"name": "bash"}}]},
        "finish_reason": "tool_calls"}]})["choices"][0]["delta"][
            "tool_calls"][0]["function"]["arguments"] == ""

# --- TurnAcc over one whole reply --------------------------------------------

acc = wisp.TurnAcc(wisp.DEFAULT_THINK_FIELDS.split(","))
acc.apply_delta(chunk)
assert [b["type"] for b in acc.blocks] == [
    "text", "tool_call", "tool_call"], acc.blocks
assert acc.blocks[0]["text"] == "the whole answer"
assert acc.blocks[1]["id"] == "call_1"
assert acc.blocks[1]["arguments"] == '{"command": "echo one"}'
assert acc.blocks[2]["id"] == "call_2"
assert acc.blocks[2]["arguments"] == '{"command": "echo two"}'
assert acc.finish_reason == "tool_calls"
assert acc.usage == [USAGE]
assert acc.cached_tokens == 3

# --- provider gate -----------------------------------------------------------

gate = world_of({"WISP_LLM_API": "anthropic", "WISP_LLM_STREAM": "false"})
try:
    wisp.build_request(gate, [])
except SystemExit as exc:
    assert exc.code == 1
else:
    raise AssertionError("stream off outside openai-chat must fail")
assert gate.get("stderr").text == (
    "wisp: WISP_LLM_STREAM=false needs WISP_LLM_API=openai-chat"
    " (got anthropic)\n"), gate.get("stderr").text

print("PASS: test_wisp_nonstream_unit")
