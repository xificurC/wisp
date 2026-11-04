# Testing

The tests hold one rule: no test needs the network, a clock, or a real
endpoint. A test that breaks the rule is a test that fails on a plane.

## The seam

wisp does all IO through a `World` object. A test builds the same world
with a different registry and swaps one service at a time:

| Service | Test double |
|---|---|
| `fs` | An in-memory tree |
| `env` | A dict |
| `clock` | A counter |
| `stdout`, `stderr` | `io.StringIO` |
| `llm` | A scripted client, or a replay |
| `session` | A real service over the fake fs |

`tests/test_wisp_world_io_seam.py` proves the seam holds. It gives wisp
a fake fs that fails on any path outside `/fake`. A direct `open`, a
direct `os.environ` read, or a direct `urllib` call raises.

The test is a probe, not a unit test. Run it with `python3`. It holds
one check with a wide reach: the whole scan path of `skill ls` and
`skill read`.

## Shell suites: a fake HTTP server, not a mock

The shell suites start `tests/fixtures/fake_llm_sse.py`. It is a small
HTTP server that replays recorded SSE streams. wisp speaks to it over
real sockets, with a real `urllib`.

Why not a mock in Python: the wire layer is the thing under test. A
mock replaces the wire. The fixture keeps the wire and replaces the
backend.

The suites also use PATH shims. A test that needs `curl` gets a script
named `curl` at the front of PATH. The script reads its arguments and
prints a recorded answer.

A shim is a last resort. It is honest about one thing: the tool is
external and the test cannot move it.

## The recording

`tests/fixtures/` holds recorded streams and usage logs:

| File | Holds |
|---|---|
| `fake_llm_sse.py` | The replay server, with modes for each case |
| `fake_curl` | A `curl` shim with canned SSE |
| `fake_curl_reasoning` | The same, with reasoning blocks |
| `fake_curl_malformed` | A malformed stream, for the error path |
| `render_event_log.jsonl` | Records for the renderer |
| `usage_event_log*.txt` | Usage chunks, in two shapes |
| `usage_net_rule.txt` | The net-token rule |

A recorded stream is truth. The test asserts on the record that wisp
writes, not on the log that wisp prints.

## Byte identity

Two invariants need byte identity:

1. **The chat body.** A stored session must send the same bytes after
   an upgrade. A changed prefix is a cache miss, and a cache miss is
   money.
2. **The system prompt.** The subagent block and the wisp block are
   pinned text. A silent edit to a law is a behavior change.

`TestChatGoldenBody` pins the chat body as one literal string. The
test fails when one byte moves.

`test_subagent_laws.py` pins the law list and the recipe text.

The rule for a change: if you change a pinned byte on purpose, update
the pin in the same commit and say why. Never regenerate a pin to make
a test pass.

## The unit suites

| Suite | How to run | Holds |
|---|---|---|
| wisp | `python3 -m pytest wisp/tests -q` | Bodies, records, compaction, steering, guard, tools |
| wispy | `python3 -m pytest wispy/tests -q` | The wrapper: phases, gates, Ctrl-C, state counting |
| tikit | `bash tikit/run_tests.sh` | 93 checks over create, query, YAML, SQL, ids |
| shell | `bash tests/test_wisp_*.sh` | 97 checks over the registry, ls, grep, commits, steering |
| seam | `python3 tests/test_wisp_world_io_seam.py` | The no-direct-IO rule |

## What the tests do not cover

- The real endpoint. `wisp/tests/smoke_paid.py` covers that, by hand,
  with a key. It is not part of the suite.
- A real terminal. The renderer is tested on recorded events.
- Concurrency. The rule is one command per session dir. A test that
  breaks the rule tests the damage, not a feature.
- Timing. A test that sleeps is a test that flakes.
