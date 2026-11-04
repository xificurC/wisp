# Commit

This is a seal, not a review. Make one commit.

Run no check. Do not run a test, lint, type check, build, or any
other verification command. The work is done when this turn starts,
and a check cannot change it: this turn stages and commits, and edits
no work. Run only the git commands and the file reads that this file
names.

## Read first

Read in this order:

- the ticket and the state above
- `states/NNN.md` and `responses/NNN.md` in the ticket dir, oldest first.
  `states/NNN.md` is the handoff that session left. `responses/NNN.md` is
  its answer.
- `sessions.txt`, one session dir per line
- the repository: `git status`, `git diff`, `git log`, and the files that
  the ticket's work touches

Do not read a `wisp.jsonl` whole. One transcript can hold hundreds of
thousands of tokens and fills the context in one read. When the derived
record does not settle a point, search the transcripts: `grep -n` for the
term, then read the lines around the hit. Never read a transcript in full.

## The ticket dir

The ticket dir holds two sets.

- Record: `ticket.md`, `STATE.md`, `states/`, `responses/`, and
  `sessions.txt`. A legacy ticket can also hold `request.md`, `.named`,
  and `frames/`. Commit the record.
- Wrapper state: `.phase`, `.seq`, `skills/`, and `personas/`. The ticket
  `.gitignore` lists them. Do not stage, commit, delete, or edit them.

`responses/NNN.md` is the work answer of session NNN. It travels with the
record, so a reader can follow the work without the transcripts. The commit
turn writes no response: every response is final before this turn.

wispy writes the ticket `.gitignore` before this turn. Commit it with the
record. Do not edit it.

The ticket dir is the group: its record travels with the work. The work can
be anywhere in the repository. The ticket record and the transcripts show
you which changes are this ticket's.

## Decide

Decide, then stage and commit. Your tool commands start in the repository
root. wispy stages no path for you.

Rules:

- Use the subject given above. Add a short body with the facts a reader
  needs: paths, ids, commands, versions.
- After the commit, the ticket dir has no uncommitted record. An
  uncommitted wrapper path is not a failure; the `.gitignore` hides it.
- Make one commit. If the user did not ask you to amend, make exactly one
  new commit and do not amend. If the user did ask, amend the HEAD commit.
  Do not rebase or reset.
- Do not push.
- wispy reads the git state, not your answer. It checks the exit code, that
  HEAD moved, and that the ticket dir has no uncommitted record. It then
  prints `git show --stat HEAD` on stderr.

Steering:

- A `<steering>` block may sit above these rules. It is the user's one-shot
  instruction for this commit, given on stdin. Without the block, select the
  paths as this file says.
- The block has priority over the path selection. It can widen the commit
  past this ticket's work ("include ticket xyz as well"), and it can skip a
  path ("skip this file"). When it widens the commit to another ticket,
  stage that ticket's dir whole, so its record travels with the work.
- The block has no priority over these: the subject above, no push, and no
  uncommitted record in the ticket dir after the commit. A skip that leaves
  a record change uncommitted cannot be honored; wispy checks that dir and
  exits 1. A skipped change outside the ticket dir stays uncommitted, and
  wispy still passes it.
- The block cannot cancel the commit. An empty commit moves no HEAD, and
  wispy exits 1.
- The block is not ticket content. Do not write it into a ticket file. The
  session transcript holds it.
