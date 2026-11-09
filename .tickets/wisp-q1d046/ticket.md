---
id: 'wisp-q1d046'
name: 'learning from the billion-context project'
status: 'closed'
created: '2026-11-09T12:45:33Z'
parent: null
blocked-on: []
---

# Scout: billion-context (BC)

Repo: `~/code/billion-context`, MIT, author Xianglei Ran. A proxy/plugin that
sits between an agent CLI and the model API and rewrites the request body.
Paper: `paper/model-driven-incremental-hierarchical-compression-...md`.
Kernel: `kernel/` (pure TS, no I/O, no model calls).

## Mechanism (kernel pipeline)

- Model window = folded digest prefix + raw recent zone (~50K). Called the fold.
- Every message gets a stable ref (`m00420`). Ranges are cited by ref.
- `compress` tool: model writes `{startRef, endRef, summary, topic}`. The
  kernel allocates a `CompressionBlock` (tier 1), records `directMessageIds`
  and transitive `effectiveMessageIds` lineage, and deactivates the range.
- Tier 2 folds blocks into blocks (`directBlockIds`); tier 3 folds tier 2.
  LSM-shaped: each piece folds once and then stays resident. Not re-summarized.
- Append-only history; compression only deactivates a mid-history range, so the
  provider prefix cache survives. That is the load-bearing difference from
  rewrite-style compaction.
- Trigger: nudge, not threshold. Fill >= 45% AND growth >= floor since the last
  compression (default 50K, effective 22.5K). Resets the baseline on success.
  Doctrine also lets the model compress with no nudge (22% of compressions).
- Nudge text carries: compressible ranges with real token sizes and tool/text
  share, active block map, growth line. It carries no fill percentage.
  The nudge is injected for the compress turn and hidden afterwards.
- Protected zones live in the filter stage, not the prompt: first user message
  pinned, recent floor, compress-call records hidden.
- Restore: `decompress` (back into context) and `decompress-to-file` (full text
  to disk, prefix preserved). `search_context` greps block summaries.

## Doctrine (the portable part)

`kernel/src/compression-rules.ts` holds four load-bearing texts:
`COMPRESS_PHILOSOPHY`, `HOW_TO_COMPRESS_RULES`, `TIER2_DISTILL_RULES`,
`TIER3_CONDENSE_RULES`. Content:
- One criterion: compress iff the current task step no longer needs it.
- KEEP VERBATIM: paths with line numbers, signatures and load-bearing code
  lines, exact error strings, decisions WITH rationale, constraints, exact
  values, goal and goal evolution, purpose per action, open questions.
- DROP: verbose logs after the error line, duplicate reads, consumed exploration,
  dead ends (keep one-line lesson), the journey to a conclusion.
- PRIORITY for tight budgets: goal > decisions+rationale > artifacts >
  conclusions > lessons.
- Recorded state is labelled history: "TASK AS OF THIS BLOCK", never a live
  directive. Quotes need a ref or become paraphrase. Open objectives re-carry
  verbatim at every tier.
- Size targets: tier-1 block ~185 tok median (<=2K); tier-2 50-150 tok/block;
  tier-3 30-60 tok/block.

# Comparison with wispy

| axis | wispy today | billion-context |
|---|---|---|
| compaction unit | whole session, at a boundary | mid-history range, many small folds |
| trigger | guard percent (70%) hard stop | fill AND growth gate, model may refuse |
| writer | model writes ticket + STATE.md, unguarded turn | model writes summary, kernel does bookkeeping |
| durability | ticket (record) + STATE.md (handoff), both rewritten | blocks with lineage, append-only state |
| reversibility | source stays in `wisp.jsonl`, reachable by path only | per-block, ref-addressable, decompress/search |
| enforcement | `check_state` notes lint problems, never fixes | kernel enforces floors and zones, prompt only requests |
| in-session cost | full history resent every round | prefix stable, folded prefix shrinks |

Measured on this repo's three live tickets (jsonl + usage, 2026-11-09):

- standing fold: `ai-wpueub` 65x, `wisp-5rva5v` 126x, `wisp-o2llma` 89x
  (bytes of all session jsonl vs ticket+STATE bytes).
- session mass: tool results 35-44%, reasoning 26-31%, tool-call arguments
  7-21%, user prompts 6-16%, system 7%, assistant text 2-3%.
- billed prompt tokens: 3.25M over 70 rounds, 14.1M over 259, 22.4M over 409.
  Peak context 78K / 125K / 160K. Resend amplification = sum/peak = 42x, 113x,
  140x. Almost all billed input is history resent, not fresh work.
- the recorded usage carries no cache fields at all. Cache-read share is
  unobservable in wispy today.
- reasoning is the second mass in a wispy session and is not a BC category;
  BC drops reasoning from compress calls (`src/reasoning-drop.ts`).

# Port candidates, cheapest first

1. Fidelity doctrine in `prompts/distill-rules.md`. Pure text, no code. Add
   KEEP VERBATIM / DROP / PRIORITY / size targets / "TASK AS OF" labelling /
   open-objective carry / quote-needs-a-pointer. Highest value per line.
2. Sizes in the distill prompt. ~40 lines in wispy: read `wisp.jsonl`, print
   per-round token totals plus tool/text share and user-message anchors.
   Gives the distill turn a real target list (BC mechanic v).
3. Band + growth gate instead of a bare percent. ~60 lines: fire the distill at
   >=45% AND growth >= floor since the last distill; drop the ratio from the
   prompt; accept a "NOT YET" reply that returns to the same session (wispy
   continue already exists).
4. Enforcement floor. Extend `check_state` from notes to gates: a Cache or
   Pointers line must name an existing source; an open objective must appear in
   the ticket or the STATE `Open`; the cap becomes a cut, not a note.
5. Refs in wisp. Number records, add `wisp slice -d DIR -n 12:40`, require
   Cache lines to cite a ref. ~60 lines, makes restore real and cheap.
6. Mid-session fold. The real port, ~250-400 lines in wisp: a `fold` record
   type that no-ops at render time by covering a record range, so `wisp.jsonl`
   stays append-only and the fold is a projection; recent-zone floor; guard
   fires a fold instead of a stop, stop stays last resort. Pays the 42-140x
   resend amplification. Costs wisp its three-tool simplicity.
7. Cache ledger. ~20 lines: record cache fields when a provider reports them,
   print per-run cache-read share, warn on collapse (BC `src/cache-ledger.ts`).
8. Tier-2 over `states/`. Only if the ticket itself outgrows its sections.
   wispy has no tier 1, so tier 2 waits.

Not portable: proxy/MITM, host adapters, plugin installers, billing, the
2600-line config surface, image rescale, output steering.

## Gaps

Which ports to take. Options:
- (a) 1-4 only: doctrine, sizes, band, enforcement. Days, no wisp change.
- (b) 1-5: adds record refs and a slice command.
- (c) 1-6: adds the mid-session fold, the only port that changes the billing
  curve.
Each option needs a user answer before the next session builds anything.
