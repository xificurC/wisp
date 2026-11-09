---
id: 'wisp-4bojxp'
name: 'elephant goldfish model - port to wisp(y)?'
status: 'wip'
created: '2026-11-09T13:44:13Z'
parent: null
blocked-on: []
---

## Research: elephant-goldfish-model (EGM)

### What EGM is

EGM is an implementation of Spec-Driven Development. Three roles bind it:
the Elephant (deep project context, drafts the spec), the Goldfish (a fresh
subagent with no conversation history, audits the draft against a rubric),
and the human (decides trade-offs, approves the spec). EGM's stated targets
are four failure modes: hallucination cascades from one long thread,
premature implementation, chat-dump fatigue, and documentation drift.

The method runs in five steps:

1. Brainstorm: open questions, then a seven-lens reviewer swarm, then
   `concepts_brief.md`.
2. Draft: `design_draft.md` section by section, one approval gate per section,
   then a reconcile against the brief, then `docs/designs/FEATURE.md`.
3. Review: five fresh-context stages: Zoom Out, Comprehension, Critic,
   Intermediate Zoom Out, Implementation Readiness.
4. Resolve: the author classifies each finding CONTEST, ESCALATE, PROPOSE FIX,
   or DECLINE, then applies approved edits.
5. Implement against the doc; run a drift report periodically.

The human owns every architectural trade-off. `egm-draft` forbids the agent
from ranking options or picking a default.

### Mechanism inventory

- 7 skills: brainstorm (1,977 words), draft (2,364), review (3,140),
  review-loop (1,402), resolve (1,195), bootstrap (2,933), drift-report (437).
- 10 persona files in `agents/`: zoom_out, comprehension, design_critic,
  structural, style, implementation_readiness, codebase_details,
  inventive_catalyst, synthesizer, bootstrap_orchestrator (196-916 words each).
- 5 rubric files in `resources/document_standards/` (182-373 words each).
- The whole corpus is 20,875 words.
- A plugin manifest fans the same files out to several harnesses. No fork of
  the skill text per harness.
- Skills assume a host subagent tool with a fresh context. EGM stops the
  review when the host cannot provide one.

### The invariant worth porting

The artifact is the only channel between the author and the reviewer. The
reviewer gets the artifact, the rubric, and a reading list. The reviewer gets
no drafting conversation. The rubric is fixed before the review and lives in
a versioned file. The human decides every trade-off. Everything else (five
stages, seven lenses, a synthesizer, re-audit caps) is scaffolding for recall
and coverage, not the method itself.

### wisp/wispy mapping

| EGM | wisp / wispy |
|---|---|
| Slash command | `wispy run --skills NAME`, or `wisp new -s` |
| Subagent tool | `wisp new --parent -s persona`, then `wisp run`, then `wisp response` |
| Named persona registration | The persona file passed to `-s` |
| Goldfish isolation | A child session with no inherited conversation |
| GoldfishContext | Paths listed in the child prompt; the child reads them |
| Document standard | A versioned file named by the skill body |
| Artifact side panel | A file in the repo |
| Synthesizer | The parent aggregates child responses |
| `ask_question` gate | A chat turn between `wispy run` calls |
| Reviewer line range | The skill reads the file and splits at `## Detailed Implementation Plan` |

### What fits cleanly

- Fresh-context review is native: `wisp new -s` fixes the whole system prompt,
  which gives stronger isolation than EGM's host harnesses, because the host
  still injects repository instruction files.
- Parallel fan-out: start N children with `&` and `wait`, one stream each,
  then read each with `wisp response`.
- The review report is a file, so the parent keeps only the deduped summary.
- Every reviewer's exact prompt and findings land in its `wisp.jsonl`. EGM's
  reviews are opaque events.
- Each child picks its own model and thinking level. EGM cannot do this.
- `wisp usage` prices each reviewer.
- Two instances of one reviewer can run and their findings diffed. Child
  sessions make the diff cheap.

### Frictions

1. Gates. `wispy` distills and clears `.phase` after every finished work run.
   It has no "the model yielded for approval" state. EGM's section-by-section
   draft and stage checkpoints assume a live session. Consequence: either a
   gate ends the session (state handoff carries the work), or wispy grows a
   gate marker that keeps `.phase` open.
2. Elephant memory. `egm-resolve` wants the session that wrote the document,
   because contesting a finding needs the earlier reasoning. A wispy distill
   discards that. The ticket must carry a Decisions section with rationale for
   a fresh session to contest credibly.
3. Nesting. EGM adds a synthesizer layer between the Elephant and reviewers.
   wisp can nest, but each layer costs a model turn and a session. Direct
   dispatch from the parent is cheaper; the synthesizer earns its cost only
   when the parent's context is scarce.
4. Prompt weight. `egm-review` alone is 3,140 words. wisp pays the system
   prompt once per session, and wispy pays it once per one-shot session.
   Porting all seven skills verbatim imports the complexity wisp avoids.
5. Read-only is instruction only. EGM's Claude adapters set read-only tools.
   A wisp child always has bash and python3. A Goldfish can write unless the
   skill forbids it and the child works outside the repo.
6. No structured question tool and no inline artifact comments. The shell is
   the UI: a gate is a run boundary plus a file the human edits.

### Options

A. Faithful plugin on wisp. Port all seven skills, ten personas, five
   standards. Closest behavior, largest prompt and maintenance cost.
B. Thin goldfish layer plus a drafting pipeline. Port the review half as
   standalone skills (review, reviewers, standards) and the draft half as a
   wispy skill. Skip bootstrap and drift at first.
C. New workflow. Long-lived plain `wisp` sessions per artifact, with children
   for review; wispy only tracks the ticket. No distill loop, no gate problem.

### Recommendation

Take B, with C as the escape hatch for interactive drafting. The review half
is the part of EGM that pays for itself, and the review half maps one-to-one
onto wisp. The draft half needs the gate decision. The brainstorm swarm and
the bootstrap skill duplicate work the existing brain/glasses/pen skills do.

Build this first:

```text
.agents/skills/
  goldfish-review/SKILL.md        # fan out, dedupe, write report
  goldfish-zoom-out/SKILL.md      # personas as skills
  goldfish-comprehension/SKILL.md
  goldfish-design/SKILL.md
  goldfish-readiness/SKILL.md
docs/standards/
  feature-spec.md
  zoom-out.md
  implementation-readiness.md
```

One child per reviewer:

```sh
CHILD="$(wisp new --name "goldfish-$NAME-$TICKET" --parent "$SELF" \
  -m "$MODEL" -t "$THINKING" --env-in-system-prompt \
  -s <(wisp build-system-prompt --wisp --skills --agents-md \
       < <(wisp skill read "goldfish-$NAME")))"
printf 'Document: %s\nLines: %s\nRubric: %s\nContext: %s\n' \
  "$DOC" "$RANGE" "$RUBRIC" "$CONTEXT" \
  | wisp run -d "$CHILD" --context-guard 70% > "$CHILD/wisp.stream"
wisp response -d "$CHILD"
```

The parent writes `review_report.md` from the child responses, dedupes the
findings, and groups them by severity. The parent never copies a full reviewer
report into another prompt.

## Gaps

Which gate model does the drafting session use? The review half needs no
decision; the three options change only the drafting half.

- Run boundary: no wispy change; each gate ends the session and distills; the
  ticket carries the decisions; the cost is a context reset per gate.
- Gate marker: a small wispy patch; a marker file keeps `.phase` open and
  skips the distill; the session survives the human reply; the cost is one new
  state in wispy's model.
- Plain `wisp` session: no wispy loop; one session runs for the whole document;
  the ticket tracks the work; the cost is that wispy's distill discipline does
  not apply.

### Sources

- ~/code/elephant-goldfish-model: README.md, docs/getting_started.md,
  docs/designs/architecture.md, docs/harnesses.md, skills/*/SKILL.md,
  agents/*.md, resources/document_standards/*.md
- ~/code/wisp: README.md, md/design/{wispy,skills,session-model}.md,
  wispy/prompts/*.md, wispy/wispy, wisp/wisp
