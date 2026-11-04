# Distill

The session is over. Distill it into the ticket and into the handoff file.
The full history stays in this session's `wisp.jsonl`. Do not copy it.

## Part 1 - the ticket

Edit the ticket file with your tools. The system prompt names the path.

Ask this of each line that the session produced: is it record, or handoff?

- Record: put it in the ticket, in the body section that owns its subject.
  A record that is not settled is a question. In a `STOP` distill it goes
  in `## Gaps`, with its options. In a `LOOP` distill it goes in the state
  `Open`, not in the ticket.
- Handoff: never in the ticket.
- Both: the ticket.

Merge, do not append. What is still true stays. What the session overturned
or completed leaves or changes. What is new enters. The file must not grow
when nothing new happened.

Add a section only when no section owns the subject. Add at most one section
in this distill. `## Gaps` does not count against this cap. Keep the
frontmatter as it is. The status is not yours. Never copy the frame.

## Part 2 - the handoff

Reply with the whole new `STATE.md`. The wrapper writes the file from your
reply. Do not write the file. Use no tool after this point. No code fence.
No preamble.

Skeleton, in this order:

```
# Next
# Open
# Cache
# Pointers
```

- `Next`: the smallest instruction that a fresh session can run without this
  transcript. One line per action.
- `Open`: in a `LOOP` distill, one line per blocking question, with its
  options. In a `STOP` distill it holds no question; that question's home
  is ticket `## Gaps`.
  A question stays a question. It moves only on a user answer or on a
  newly true fact. No later session turns a waiting line into an answer.
- `Cache`: a handoff fact that cost more than one read. The test is the
  price: the derivation read two or more files, joined two sources, or
  repeated a search. Write the fact in full, then its sources, then its
  target:

  ```
  - <fact in full>. (From: <source 1>, <source 2>) (Serves: Next)
  ```

  `Serves:` is `Next`, `Open`, `task N`, or `cold`. `cold` means that no
  pending step needs the line. A fact that one read rebuilds stays in `Next`
  or `Pointers`, with the read named. A cache line does not become a record.
- `Pointers`: paths, session dirs, commands, ids. Exact. Record no commit
  hash. A commit that carries this state does not exist when you write it,
  and a hash of an earlier commit goes stale. Name the branch and the
  session dirs instead.

The ticket travels with every prompt. Do not restate a record here. The
state is the handoff plus the cache, not a log.

Cut order, when the file is over the cap:

1. a `cold` `Cache` line,
2. a `Cache` line that the ticket and `Next` both cover,
3. the oldest line.

The cap is @@CAP@@ non-empty lines. The mode is @@MODE@@.

- `LOOP`: the next session runs. An open question may stay in `Open` when
  the next session can answer it. It does not go to ticket `Gaps`.
- `STOP`: the work stops here. An open question that still matters goes to
  ticket `Gaps`. It stays a question, not a fact. It does not go in the
  state `Open`.

Do not commit in this turn. The next step is the user's: `wispy
commit`, `wispy run` again, or `wispy continue`. If the user did not
explicitly request a commit, don't.
