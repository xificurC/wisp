---
id: 'wisp-gkk6yp'
name: 'wispy commit can close but commit message says wip'
status: 'closed'
created: '2026-11-10T11:59:12Z'
parent: null
blocked-on: []
---

## Diagnosis

The commit subject is frozen before the commit session starts.

1. `cmd_commit` opens the ticket (`wispy/wispy:1067`) and keeps the
   frontmatter status from that read. At this point the status is `wip`.
2. `commit_turn` renders `Ticket status: wip` and the literal subject
   `wip(<id>): <name>` from `commit_subject` (`wispy/wispy:538`) into the
   prompt text (`wispy/wispy:610`).
3. The `<steering>` block `close then commit` follows that header. It
   makes the session edit `ticket.md` to `status: 'closed'` and commit.
4. `prompts/commit-rules.md` says "Use the subject given above." The
   session obeys and commits the frozen `wip(...)` subject while the
   committed `ticket.md` says `closed`.
5. `cmd_commit` never re-reads the ticket after the session and never
   re-derives the subject. Its post-run checks cover only the exit code,
   that HEAD moved, and that the ticket dir is clean.

Closing is model work under steering, not a wispy verb: `COMMANDS` holds
`run`, `continue`, `steer`, `commit`, `response`, and no source path
writes `closed`.

Reproduced model-free with `wispy/tests/test_wispy.py`: a dirty tree,
stdin `close the ticket, then commit`, and an `on_stream` hook that
rewrites the ticket to `closed`. The streamed prompt holds
`Ticket status: wip` and `wip(ai-test): Test ticket`, and `ticket.md`
ends `closed`.

Real instance in this repository: commit `93d864d` has subject
`wip(ai-wpueub): wispies`, and its committed
`.tickets/ai-wpueub/ticket.md` says `status: 'closed'`. Its body even says
"User steering closed the ticket." The route that works is a close in an
earlier session, then commit: `44d5231` reads
`closed(wisp-elak2h): ...` because the close landed before the prompt was
built.

## Decision

C landed: `wispy commit --close` sets the ticket status to `closed` before
the prompt is built. `mark_closed` (`wispy/wispy:367`) runs after the phase
and repo gates and before the work-tree check, so the status change is
record that the commit session stages. The subject, the prompt header, and
the ticket record then agree. The flag is refused outside `commit`. Six
tests in `wispy/tests/test_wispy.py` cover the prompt, the open and closed
inputs, the phase gate, the refusal, and the clean-tree start; the suite
runs 97 tests, all passing. The flag is documented in the script docstring,
the Flags list, and `md/design/wispy.md`.

Rejected: A (amend after the fact) rewrites a landed commit; B only
reports the mismatch; D leaves the outcome to the model.

## Gaps

Which fix should land for the stale commit subject? Options (settled: C):

- A: `cmd_commit` re-reads the ticket after the session. When the status
  changed, it rewrites the first line of the commit message from
  `git log -1 --format=%B` and `git commit --amend -F -`.
- B: `cmd_commit` fails after such a status change with a repair note, so
  the mismatch cannot land silently.
- C: a `close` verb or a `--close` flag on `wispy commit` sets the status
  before the prompt is built, so the subject comes out `closed`.
- D: `commit-rules.md` tells the session to re-derive the subject after
  any close. This leaves the outcome to the model.
