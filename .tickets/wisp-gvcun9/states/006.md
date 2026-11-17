# Next
- Take no code action: the streaming passes are implemented, tested, and uncommitted; the next move is the user's (`wispy commit`, `wispy run`, or nothing).
- Read ticket `### Fourth pass: the argument freeze is the endpoint's chunking` before touching the renderer again; the stall is upstream, not a renderer fault.
- Leave `wisp/tests/test_attachments.py::TestChatGoldenBody::test_golden` alone unless the user asks; the ticket records why.
- Build a waiting placeholder in `Renderer.tool_delta` only on an explicit user request; nothing is scheduled.

# Open
- None.

# Cache
- `deepseek-v4.1-flash` streams tool-call arguments in 5 fragments with a 5.02 s gap and one 6.6 kB final fragment; `glm-5.3-flash`, `mimo-2.6-flash`, and `laguna-s-2.1` stream 1633/1720/1812 fragments with gaps of 0.19/0.07/0.07 s, and `qwen3.8-27b` streams 455 fragments with one 1.31 s pause. The coarse chunking is that model path's property on the company LiteLLM endpoint, not wisp's. (From: probe runs against `$WISP_LLM_URL` with a 6.5 kB heredoc prompt, nonce per run) (Serves: Next)
- wisp adds no delay: the renderer wrote the fence at 0.840 s, the first argument text at 0.900 s, and the rest at 2.169 s, while the raw `wisp run` stream carried the same two fragments at 1.015 s and 2.269 s. (From: `/tmp/render_stamped.txt`, `/tmp/wisp_probe_stamped.txt`, `probe/stamp_bytes.py`) (Serves: Next)
- LiteLLM's response cache replays a finished turn as one chunk; a nonce in the prompt is needed to measure live chunking. (From: probe run with and without a nonce) (Serves: Next)
- Test baseline: `python3 -m pytest wisp/tests tests -q` gives 192 passed, 1 failed (the pre-existing `test_attachments` golden); shell suites `tests/test_wisp_run_nonstream.sh` 5/5, `tests/test_wisp_per_round_commit.sh` 4/4, `test_wisp_stop_tool_call.sh` 1/1, `test_wisp_registry.sh` 11/11, `test_wisp_sub_recipe.sh` 12/12. (From: previous session's runs) (Serves: cold)
- The golden-body failure predates the streaming work: stashing `wisp/wisp` and rerunning still fails on HEAD, because the golden pins an older python3 tool description. (From: `wisp/tests/test_attachments.py:237`, stash rerun) (Serves: cold)
- Live and replay stay byte-identical: `diff -u` of `render-live` and `render-past` on a `fake_llm_sse.py tworound` run differs only in the `[user]` block that render-past adds. (From: live run, diff) (Serves: cold)

# Pointers
- Ticket: /home/pnagyux/code/wisp/.tickets/wisp-gvcun9/ticket.md
- Source: /home/pnagyux/code/wisp/wisp/wisp
- New test: /home/pnagyux/code/wisp/wisp/tests/test_stream_render.py
- Updated tests: /home/pnagyux/code/wisp/wisp/tests/test_tool_result_reset.py, /home/pnagyux/code/wisp/tests/test_wisp_tool_status.py, /home/pnagyux/code/wisp/tests/test_wisp_run_nonstream.sh, /home/pnagyux/code/wisp/tests/test_wisp_per_round_commit.sh
- Design records: /home/pnagyux/code/wisp/md/design/tool-result-status.md, last section "The call fence names its language (2026-11-17)"
- Probes: /home/pnagyux/code/wisp/wisp-sessions/wisp-gvcun9-006/probe/provider_timeline.py (run as `python3 provider_timeline.py MODEL - < prompt.txt`), probe/stamp.py, probe/stamp_bytes.py
- Probe prompt: /tmp/probe_prompt_big.txt (6.5 kB heredoc); results: /tmp/res_<model>.txt
- Branch: main, working tree uncommitted
- Session dirs: /home/pnagyux/code/wisp/wisp-sessions/wisp-gvcun9-006 (this session), /home/pnagyux/code/wisp/wisp-sessions/wisp-gvcun9-005 (renderer access), /home/pnagyux/code/wisp/wisp-sessions/wisp-gvcun9-004 (streaming implementation), /home/pnagyux/code/wisp/wisp-sessions/wisp-gvcun9-001 (scout transcript)
