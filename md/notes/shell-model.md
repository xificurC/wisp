# The shell model: one shot, with file carryover

This note answers one question. Does an agent keep a shell alive across
its run, or does it start one shell per call?

The answer here is one shot. State lives in files. A live shell is not
state.

## The question

A persistent shell saves steps. The model does not retype `cd`, and it
does not re-export a variable. The saving grows with the length of a
stateful loop: build, serve, probe.

A persistent shell also hides state. The working dir, the environment,
the open files, and the background jobs sit in a process that the
harness cannot read, save, or replay.

So the real question is: which state must live in a process, and can a
file carry it instead?

## What the frameworks do

| Framework | Shell mode | How |
|---|---|---|
| OpenHands | Persistent | One container with a live bash shell per run |
| terminal-bench | Persistent | One tmux session per task |
| SWE-agent | Persistent | One bash session per task through its runtime |
| E2B | Persistent filesystem | A sandbox with a filesystem that outlives a call |
| Aider | One shot | A fresh subprocess per command |
| Claude Code | One shot, with carryover | A fresh process per command; the working dir carries over |

Two other agent CLIs in the survey also use a fresh child process per
call. Both pass the working dir and the environment explicitly. Neither
keeps a shell heap.

The split is real. The benchmark runners choose persistent. The
general-purpose coding tools choose one shot.

No paper isolates the variable. A search of arXiv found no ablation
that runs one agent on one task under both modes. The evidence is
design docs, and design docs state one mode without a comparison.

## The decision

Adopt one shot with file-backed carryover.

| Primitive | Carries | Cost |
|---|---|---|
| A named env file | The startup environment | One read per call |
| The working dir as a value | `cd` across calls | One field in the call |
| A supervised process helper | One long-running server | A PID file, a log, a status file |

The first two recover most of the token saving. They cost no risk.

The third is optional. Use it only for a task that needs one live
process. It stays file-backed: a PID file, a log file, a status file.

## What the decision rejects

### The persistent shell

A live bash process holds its state in a heap. The harness cannot read
that heap, save it, or replay it. Three properties break:

- A replay depends on call order and hidden state. It cannot be
  deterministic.
- A test that swaps the filesystem cannot see the heap.
- The sandbox must hold a live process, so the blast radius grows.

The shell saves one `cd` per call. It costs the ability to reproduce a
run.

### The REPL kernel

A kernel holds the largest opaque state: variables, imports, and an
object graph. It is the least visible and the hardest to replay.

### A session shared across agents

One session belongs to one agent across its own turns. A session that
two live agents can see collides with parallel work. Two writers to one
heap lose an update.

## The rule

A directory is state.

Every value that must outlive one tool call lives in a file in the run
tree. A file is visible, durable, and replayable. A process heap is
none of those.

The rule gives three checks for a new feature:

1. Where does the state live? If the answer is "in memory", the design
   is wrong.
2. Can a second process read it? If not, no tool can observe the run.
3. Can a test write it before the call? If not, the test needs a live
   process.

## How wisp applies the rule

wisp runs one fresh child per tool call. The call passes a command
string. The child gets its own process session, so a timeout can kill
the whole tree.

Nothing carries over between two calls:

- The working dir resets.
- An exported variable is gone.
- A background job dies with the tree.

The state lives in the session dir. A command writes a file, and the
next command reads it. The model must pass a path or use a
`cd ... && ...` one-liner.

The cost is visible in a long loop: the model repeats a path. The gain
is a record that a test and a replay can reproduce byte for byte.

That trade is the point of the whole tool. The session dir is the
interface, and a live shell would be a second, invisible one.
