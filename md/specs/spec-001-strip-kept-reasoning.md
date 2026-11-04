# WISP-001 - Strip reasoning blocks from kept records

- ID: WISP-001
- Date: 2026-09-25
- Status: closed
- Component: `wisp/wisp`
- Source: falsifier review of wisp caching, 2026-09-25

## 1. Background

1. A compact session swaps each finished segment for one kept assistant record. `finalize_segment` (line 758) does this swap.
2. The swap keeps the final assistant record as-is. The final round can hold reasoning blocks.
3. `message_of` (line 2367) replays reasoning blocks as `reasoning_content` in every later request.
4. Test data, session `ebcv5h0h`: kept record 1 held 8090 chars of reasoning. Kept record 2 held 30225 chars. The first request of turn 3 held 15482 prompt tokens. About 63 percent of those tokens came from kept reasoning.
5. Each new turn adds the reasoning of its final round to the permanent request base. The base grows without limit. Compact mode exists to bound this base.
6. The NOTICE already orders the model to move every durable fact from its thinking into the kept text. The raw reasoning is redundant data.
7. The backend in use (GLM 5.3) reports no cache reads. The dead tokens bill at full input price in every round.

## 2. Scope

In scope:
- The strip of reasoning blocks from kept records in `finalize_segment`.
- One new field in the compact log line.
- Tests and docstring updates.

Out of scope:
- Replay of reasoning inside one segment. Some APIs require reasoning items or thinking blocks during a tool loop.
- Non-compact sessions.
- The archive format.

## 3. Requirements

- R1: `finalize_segment` shall remove every output block of type `reasoning` from the kept record before the commit.
- R2: `finalize_segment` shall not remove text blocks or tool blocks.
- R3: `wisp_compaction_archive` shall keep the full original records, with reasoning.
- R4: The compact log line shall show the count of dropped reasoning chars. Format: `compact round=N archive=M reasoning=K`.
- R5: `message_of` shall stay unchanged.
- R6: wisp shall not strip reasoning at load time from records that were committed before this change. A load-time strip would change bytes that earlier requests held. This would break prefix stability.
- R7: `wisp render-live` and `wisp uncompact` shall keep their function. The archive holds the reasoning for full replay.

## 4. Design note

The strip is safe for byte stability. The kept record enters the wire for the first time in the next request. The strip cannot change bytes that any earlier request held.

Reference change in `finalize_segment`, after `kept = records[-1]`:

    dropped = sum(len(b.get("text") or "") for b in kept.get("output", [])
                  if b.get("type") == "reasoning")
    kept["output"] = [b for b in kept.get("output", [])
                      if b.get("type") != "reasoning"]

Pass `dropped` to the log call in the `cut` branch.

Decision note (WBS 1.1): The strip point is `finalize_segment` in
`wisp/wisp`, right after `kept = records[-1]`, before the archive
attach and the cut log line. `records[-1]` is the stop-finish
assistant record that `loop_rounds` appends just before the call, and
`commit_round` runs only after `finalize_segment` returns. So the
strip precedes the commit on every finalize path, cut and turn end.
The kept record first enters the wire in the request after the
finalize, so the strip cannot change bytes that an earlier request
held.

## 5. Work breakdown structure

1. Design
   1.1 Confirm the strip point.
       Task: Read `finalize_segment`. Confirm that `records[-1]` is the final assistant record and that the swap runs before the commit.
       Deliverable: One decision note in this file, section 4.
       Done when: The note states the strip point and the commit order.

   1.2 Define the strip rule and the log field.
       Task: Write the filter for block type `reasoning`. Define the log field `reasoning=K`.
       Deliverable: Section 3 and section 4 of this spec.
       Done when: R1 to R4 cover the rule with no open choice.

2. Implementation
   2.1 Apply the strip in `finalize_segment`.
       Task: Add the reference change from section 4. Apply it on every finalize path, cut and turn end.
       Deliverable: Patched `wisp/wisp`.
       Done when: R1, R2 and R6 hold.

   2.2 Add the log field.
       Task: Extend the `cut` log line with `reasoning=K`.
       Deliverable: Patched log call.
       Done when: R4 holds.

   2.3 Update the docstrings.
       Task: Update the docstrings of `finalize_segment` and the module header. State that kept records carry no reasoning and that archives keep it.
       Deliverable: Patched docstrings.
       Done when: No docstring claims that kept records keep reasoning.

3. Tests
   3.1 Unit test - kept record holds no reasoning.
       Task: Build one segment with a final record that holds reasoning and text. Run `finalize_segment`. Check the kept record.
       Done when: The kept record holds only the text block.

   3.2 Unit test - archive keeps the full records.
       Task: Run `finalize_segment` on the same segment. Check `wisp_compaction_archive`.
       Done when: The archive holds the original records with reasoning.

   3.3 Unit test - in-segment replay stays.
       Task: Run `message_of` on a segment record with reasoning. Check the wire message.
       Done when: The wire message holds `reasoning_content`.

   3.4 Unit test - load does not strip.
       Task: Load a jsonl file with a kept record that holds reasoning. Check the in-memory record.
       Done when: The record keeps its reasoning blocks.

   3.5 Integration test - two compactions.
       Task: Run one compact session with inner rounds. Read `wisp.usage`.
       Done when: The prompt token count of the first round after each compaction matches the sum of system, user, kept texts, and continue records, plus 10 percent tolerance.

4. Verification and closure
   4.1 Run the full test suite.
       Done when: All tests pass.

   4.2 Measure the gain.
       Task: Run one compact session with heavy thinking, as in `ebcv5h0h`. Compare the first-round prompt tokens of turn 3 before and after this change.
       Done when: The prompt tokens drop by the size of the kept reasoning.

   4.3 Close the spec.
       Task: Mark the status `closed`. Record the measured numbers in this file.

## 6. Acceptance criteria

- AC1: After any compaction, the committed kept record in `wisp.jsonl` holds no output block of type `reasoning`.
- AC2: The archive of the same compaction holds the full original records.
- AC3: The compact log line shows `reasoning=K`.
- AC4: All tests in work packages 3.1 to 3.5 pass.
- AC5: A session resumed after the change keeps prefix stability. The cache hit rate on a cache-reporting backend does not drop.

## 7. Risks

- Risk: A backend requires `reasoning_content` in later turns. Chance: low. The in-segment replay stays, and the kept record is new to the wire in the next request.
- Risk: `wisp render-live` shows less detail for kept messages. Chance: certain. The archive keeps the data. `wisp uncompact` restores it.
## 6.3 Measured numbers (work package 4.2)

Session verify-001-42: `wisp new --name verify-001-42 -m "GLM 5.3"
-t high --compact --compact-inner-rounds 13`. Three turns, each a
small analysis task; 2, 2 and 3 rounds, under the 20-round bound.

- Turn 3 first round: usage chunk 4, actual prompt tokens 1284.
- Estimate with the bound constants A = 3.1, B = 0.23411 over the
  request-body build from the session's own wisp.jsonl: 1268 tokens
  on 5404 body chars. Deviation 1.2 percent — inside the bound 10
  percent.
- The 5404 chars cover the prompts, kept texts and the tool spec; the
  240 kept-reasoning chars held in the archives are absent from the
  wire. Adding them at B would put about 56 tokens (about 4.4 percent)
  back into the request.

Session verify-001-3p5 (work package 3.5, live once): 48-slice task
over the wisp file, inner rounds 13. Two mid-turn cuts: `compact
round=14 archive=27 reasoning=2284` and `compact round=28 archive=26
reasoning=0`. Both checked first-round points sit within the bound 10
percent of the estimate with unchanged constants. Kept outputs hold
only text blocks; archives keep the full originals.
