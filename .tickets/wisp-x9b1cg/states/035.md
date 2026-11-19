The ticket already owns every record from this session: Round 30 at line 651, four Verified rows at 834+, N26 settled in both `## Gaps` and `## Settled`, and the build-order amendment. No further ticket edit is needed; the session merged its records as it went.

# Next
- The owner's next ask gates code; every open question lives in ticket `## Gaps`: N20-N22 (agent/rule split, event disjunction, failure report as input) and Q7, Q15, Q17, Q18, Q19, Q31, Q33, N1-N8.
- Run `cd /home/pnagyux/code/wisp && python3 ember/tests/test_flow.py` (230 checks, about 125 s, no paid call) before and after any change to `ember/ember`.
- Keep `wisp/wisp` unchanged; the nine wisp changes stand.

# Open

# Cache
- The state root holds `ember.db`, `ember.sock`, `ember.pid`, `ember.log`, one stem `ember.<kind>` for every file the program writes; `daemon` names the process and only the process. The round-29 `retire_legacy` retirement is deleted outright (constants, function, call, and `send_request`'s `path` parameter), and `checks_rename` asserts the string is absent from the source, so no later session should trust a stale note about legacy retirement. (From: `ember/ember` `state_root`, `db_path`, `socket_path`; ticket Round 30) (Serves: Next)
- `ember answer RID --dismiss` (N26 a, landed): `command_answer` refuses `--field`/`-F` beside the flag and routes `dismiss` through the daemon; `apply_answer` runs it after the manual-and-waiting checks, calls `finish_failed(conn, space, row, "dismissed")`, then pump, closure, settle; the fault atoms `run:RID.failed` and `agent-type:LABEL.failed` carry `value=dismissed`; a loop rule keyed on the verdict field does not fire, because a dismissal writes the fault verb. (From: `ember/ember` `command_answer`, `apply_answer`, `finish_failed`; `flow_gate`) (Serves: Next)
- The human gate's load-bearing facts: `NONTERMINAL` includes `waiting` while `LIVE_STATES` does not, so a gate blocks settlement and closure and holds no cap slot; `answer_of_row` reads the row's stored `answer` text for `mode manual`; `apply_answer` type-checks declared fields through `typed_value`, shared with `ember result set`; `reconcile_space` skips `waiting` and `mode manual`, so a daemon restart leaves a dirless gate waiting. (From: `ember/ember` `NONTERMINAL`, `answer_of_row`, `apply_answer`, `reconcile_space`) (Serves: Next)
- Unit-check sections (`checks_*`) that call daemon-side functions using `tx()` must `conn.commit()` first: the setup `INSERT`s and `write_atom` calls open an implicit sqlite transaction that stays open, and `tx()` fails with `cannot start a transaction within a transaction`. Refusal-only calls are safe before the commit; place the commit after the last setup write. (From: `ember/tests/test_flow.py` `checks_gate`, `ember/ember` `tx` 585) (Serves: Next)
- The fake endpoint keys a run's behavior on the briefing's `agent X` line, and a manual gate never reaches the endpoint, so a gate flow needs no endpoint change; the human side is scripted through `ember answer RID --field F=V -F FILE` (or `--dismiss`) and `run(..., check_rc=False)` asserts the exit-2 refusals. (From: `ember/tests/fake_model.py` `plan`, `ember/tests/test_flow.py` `flow_gate`) (Serves: Next)
- Unit-check sections load `ember/ember` through `SourceFileLoader` under `sys.dont_write_bytecode` and hand-build run rows as plain dicts, so column readers must tolerate missing keys; `write_atom` stamps `now_iso()` itself; a bool atom stores the text `True`/`False`, which `value_of_atom` parses back; `atoms(space)` in the test helpers returns `fields` as a raw JSON string, so parse it before reading `red`. (From: `ember/tests/test_flow.py` `checks_gate`, `atoms`; `ember/ember` `_row_get`, `write_atom`) (Serves: Next)
- `py_compile` on `ember/ember` writes `ember/__pycache__/embercpython-312.pyc`, a stray artifact; delete the `__pycache__` directories after compiling. (From: this session's `py_compile` run) (Serves: cold)

# Pointers
- Ticket: `/home/pnagyux/code/wisp/.tickets/wisp-x9b1cg/ticket.md` (1157 lines; Round 30 at 651; round-30 `## Verified` rows at 834-837; N26 settled in Gaps and Settled; open: N20-N22, Q7, Q15, Q17, Q18, Q19, Q31, Q33, N1-N8)
- Design: `/home/pnagyux/code/wisp/.tickets/wisp-x9b1cg/rule-language.md` (1738 lines; §0.8; §4.15 human gates with the round-30 dismissal paragraph; §8 N-questions at the end)
- Ember: `/home/pnagyux/code/wisp/ember/ember` (3370 lines; `NONTERMINAL` 65, `Daemon`, `reconcile_space`, `socket_path`, `apply_answer`, `command_answer`, `command_daemon`)
- Ember docs: `/home/pnagyux/code/wisp/ember/README.md` (555 lines; "Why a daemon", the stem rule in "Layout", "Human gates" with `--dismiss`, the verb list, the tests paragraph at 230 checks)
- Ember tests: `/home/pnagyux/code/wisp/ember/tests/test_flow.py` (1182 lines, 230 checks), `/home/pnagyux/code/wisp/ember/tests/fake_model.py`
- Wisp source: `/home/pnagyux/code/wisp/wisp/wisp` (unchanged this session)
- Branch `main`; `ember/` is untracked; no commit
- Session dir: `/home/pnagyux/code/wisp/wisp-sessions/wisp-x9b1cg-035`; prior `wisp-x9b1cg-034`
