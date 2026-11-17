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

## The name

Part of this commit is the ticket name. Write the name before you stage,
because the subject carries it.

The name in the frontmatter now was written before the work was done. It
often states the request, not the work:

    can wisp render-live stream tool calls?

Write the work done instead:

    wisp render-live: stream tool calls and their results

A name holds when it meets every line:

- the name defines the work done, not the question that opened it
- the name is a short noun phrase, or `<component>: <effect>` with a colon
- the name is lowercase and carries no trailing question mark
- the name leads with no interrogative or auxiliary word: can, should,
  shall, does, do, is, are, was, were, how, why, what, when, where,
  which, who, whom, whose, will, would, could, did, has, have, had
- the name runs at most 12 words

Edit the `name:` line in the ticket frontmatter with your tools. The
ticket record is part of this commit, so the rename travels with the
work. Leave the other frontmatter fields as they are: the name is the one
field this turn writes.

A name that already defines the work stays. Do not invent a rename when
the work and the name agree.

After this session wispy reads the committed name and the commit subject.
When the name asks a question, runs past 12 words, or the subject carries
a name that the ticket does not hold, wispy sends one repair turn, under
`## The repair turn`. Read your own name back from the ticket before you
build the subject.

## The repair turn

wispy checks the sealed commit when this session ends. When the check
fails, wispy sends one more turn to this same session: the ticket, the
failure, and the order to repair. That turn edits the `name:` line,
stages the ticket record, and runs `git commit --amend` so the subject
carries the new name. The turn makes no new commit and pushes nothing.

A failure that survives the repair turn stands. wispy accepts the commit
and prints it. The seal has no human gate: the operator never edits a
name by hand and never amends by hand.

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

- Build the subject as `<status>(<id>): <name>` from the two values in
  the header and the name you wrote. Add a short body with the facts a
  reader needs: paths, ids, commands, versions.
- After the commit, the ticket dir has no uncommitted record. An
  uncommitted wrapper path is not a failure; the `.gitignore` hides it.
- Make one commit. If the user did not ask you to amend, make exactly one
  new commit and do not amend. If the user did ask, or wispy sent a repair
  turn, amend the HEAD commit. Do not rebase or reset.
- Do not push.
- wispy reads the git state, not your answer. It checks the exit code, that
  HEAD moved, that the ticket dir has no uncommitted record, that the
  committed name holds the definition rule, and that the subject carries
  that name. A name check that fails brings one repair turn; a failure
  that survives the repair turn stands. wispy then prints
  `git show --stat HEAD` on stderr.

Steering:

- A `<steering>` block may sit above these rules. It is the user's one-shot
  instruction for this commit, given on stdin. Without the block, select the
  paths as this file says.
- The block has priority over the path selection. It can widen the commit
  past this ticket's work ("include ticket xyz as well"), and it can skip a
  path ("skip this file"). When it widens the commit to another ticket,
  stage that ticket's dir whole, so its record travels with the work.
- The block has no priority over these: the subject rule and the name
  rule, no push, and no uncommitted record in the ticket dir after the
  commit. A skip that leaves a record change uncommitted cannot be
  honored; wispy checks that dir and exits 1. A skipped change outside the
  ticket dir stays uncommitted, and wispy still passes it.
- The block cannot cancel the commit. An empty commit moves no HEAD, and
  wispy exits 1.
- The block is not ticket content. Do not write it into a ticket file. The
  session transcript holds it.
