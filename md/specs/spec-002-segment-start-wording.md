# WISP-002 - Compaction wording: segment start, not whole turn

- ID: WISP-002
- Date: 2026-09-25
- Status: closed
- Component: `wisp/wisp`
- Source: falsifier review of wisp caching, 2026-09-25
- Depends on: none. Pairs with WISP-001.

## 1. Background

1. Three text constants drive what a kept message holds: `NOTICE` (line 691), `CUT_REQUEST` (line 698), and `ROUND_REMINDER` (line 706).
2. All kept messages persist. `load_events` loads them. `message_of` replays them in every later request.
3. With `--compact-inner-rounds`, one turn holds several segments. The current texts order the model to re-carry the whole turn in each kept message. The earlier kept messages stay in the conversation, so the re-carry writes the same facts twice.
4. Test data, session `9ub2gksu`: kept message 2 held 11018 chars against 7596 in kept message 1, and repeated its sections. The prompt floor grew from 4804 tokens (round 14) to 7715 (round 27), a 60 percent rise after one compaction.
5. The correct scope is the segment, not the turn. The segment is the records since the segment start. The segment start is the last `continue` record, or the user prompt of the turn when no `continue` record exists.
6. This is the same boundary that the code uses. `segment_start` (line 733) finds the last user record that is not a scaffold.
7. The first cut request in a turn has no earlier `continue` record. The wording must cover this case.

## 2. Scope

In scope:
- New text for `NOTICE`, `CUT_REQUEST`, and `ROUND_REMINDER`.
- Phrase checks and one guided test session.

Out of scope:
- The strip of reasoning blocks. See WISP-001.
- The archive format and the render texts.

## 3. Requirements

- R1: Each constant shall name the scope as "since the segment start".
- R2: `NOTICE` and `CUT_REQUEST` shall define the segment start: "the last 'continue' record, or the prompt of this turn when no 'continue' record exists."
- R3: Each constant shall state that earlier kept messages stay visible and that the model shall not repeat their content.
- R4: No constant shall contain "so far this turn", "stand alone", or "context-free".
- R5: The replacement texts shall keep the instruction to open with a `Kept context` section, then give the answer.
- R6: `ROUND_REMINDER` shall stay short. It rides the first tool result of every round.

## 4. Target texts

    NOTICE = (
        "[Session note: only kept messages persist in this session. Open"
        " your next plain final message with a 'Kept context' section:"
        " every durable fact from your thinking and tool calls since the"
        " segment start. The segment start is the last 'continue' record,"
        " or the prompt of this turn when no 'continue' record exists."
        " Earlier kept messages stay visible to you; do not repeat their"
        " content. Then give the complete answer.]"
    )

    CUT_REQUEST = (
        "Round limit reached. Emit the compaction now as your next final"
        " message: open with 'Kept context' - every durable fact from the"
        " work since the segment start - then one line on where the task"
        " stands and what remains. The segment start is the last 'continue'"
        " record, or the prompt of this turn when no 'continue' record"
        " exists. This message replaces the work since the segment start."
        " Earlier kept messages stay visible to you; do not repeat their"
        " content. You may call tools to re-check facts first."
    )

    ROUND_REMINDER = (
        "Reminder: only your final message is kept. Give kept context for"
        " the work since the segment start first, then the answer. Earlier"
        " kept messages stay visible."
    )

## 5. Work breakdown structure

1. Text design
   1.1 Fix the scope term.
       Task: Define "segment start" as in section 1, item 5. Match the `segment_start` code boundary.
       Deliverable: Section 3, R1 and R2.
       Done when: The term covers both cases, with and without an earlier `continue` record.

   1.2 Write the three target texts.
       Task: Write the texts in section 4. Keep `ROUND_REMINDER` under 30 words.
       Deliverable: Section 4.
       Done when: R3 to R6 hold.

2. Implementation
   2.1 Replace the constants.
       Task: Replace `NOTICE`, `CUT_REQUEST`, and `ROUND_REMINDER` with the target texts.
       Deliverable: Patched `wisp/wisp`.
       Done when: The phrases in section 6, items AC1 to AC3, hold.

   2.2 Check the users of the constants.
       Task: Read `build_request`, `loop_rounds`, and `with_round_reminder`. Confirm that no caller depends on the old wording.
       Deliverable: One check note in the merge request.
       Done when: No caller change is needed.

   2.3 Update the docstrings.
       Task: Update every docstring that repeats the old wording, for example "stand alone".
       Deliverable: Patched docstrings.
       Done when: A search for the old phrases returns no hit in `wisp/wisp`.

3. Tests
   3.1 Phrase checks.
       Task: Assert that each constant contains "since the segment start". Assert that `NOTICE` and `CUT_REQUEST` contain the segment-start definition. Assert that no constant contains a phrase from R4.
       Done when: The checks pass.

   3.2 Guided test session.
       Task: Run one compact session with `--compact-inner-rounds 13` and a task that fills more than 26 rounds. Read `wisp.jsonl` and `wisp.usage`.
       Done when: The session ends with no error and produces at least 2 kept messages.

4. Verification and closure
   4.1 Check the second kept message.
       Task: Compare kept message 2 with kept message 1 from the test session. Measure the shared 5-gram set of the two texts.
       Done when: Kept message 2 shares less than 30 percent of its 5-gram set with kept message 1, or the review accepts the excess with a stated cause.

   4.2 Check the prompt floor.
       Task: Read the prompt token count of the first round after the second compaction.
       Done when: The count stays below the count of the first round after the first compaction, plus the token size of kept message 2, plus 10 percent tolerance.

   4.3 Check the first cut case.
       Task: Read kept message 1 from the same session. Confirm that it covers the facts of the first segment.
       Done when: The message holds the task state and the key facts of segment 1. This is a manual review.

   4.4 Close the spec.
       Task: Mark the status `closed`. Record the measured numbers in this file.

## 6. Acceptance criteria

- AC1: Each constant contains "since the segment start".
- AC2: `NOTICE` and `CUT_REQUEST` contain the sentence "The segment start is the last 'continue' record, or the prompt of this turn when no 'continue' record exists."
- AC3: Each constant contains "Earlier kept messages stay visible".
- AC4: No constant contains "so far this turn", "stand alone", or "context-free".
- AC5: Work packages 4.1 to 4.3 pass on the guided test session.

## 7. Risks

- Risk: The model writes too little context, because it trusts the earlier kept messages. Chance: medium. The texts still order a full `Kept context` section for the work since the segment start. Work package 4.3 checks this.
- Risk: Old sessions lose their cache prefix once, because the texts change request bytes. Chance: certain. The cost is one cache write per resumed session. This spec accepts the cost.

## 8. Results

Session `verify-002-guided`, model `GLM 5.3 Flash`, thinking `high`,
`--compact --compact-inner-rounds 13`. Task: read `wisp/wisp` (2899
lines) in exact 60-line slices, one python3 tool call per round. The
model stopped after the cut and after the finalize, so continued
prompts resumed it; the run covers the file to line 2899 and lists
every range read in the last kept messages. One cut per resumed run
logged `compact round=14`.

- WP 4.1: kept message 1 (the cut output, 1323 tokens) and kept
  message 2 (the finalize, 747 tokens). Word 5-grams of the two
  texts: kept 1 holds 559, kept 2 holds 315, shared set 16. Kept 2
  shares 5.1 percent of its 5-gram set with kept 1. Below 30 percent.
- WP 4.2: first round after the first compaction: 1897 prompt tokens.
  Kept message 2 token size: 747. First round after the second
  compaction: 2827 prompt tokens. Limit: 1897 + 747 + 10 percent =
  2908. 2827 stays below the limit.
- WP 4.3: kept message 1 holds the task, the method, the file facts
  (2899 lines, 119691 bytes), the slices read (1 to 780), and a
  content summary of lines 1 to 780. Spot checks of the line numbers
  and names against `wisp/wisp` match. Pass.

Tests: `tests/test_segment_start_wording.py`, 5 tests. Full suite:
11 tests, OK.

Amendment (spec-003, steering), applied in two steps:

1. NOTICE and CUT_REQUEST carry one added sentence, "A steering
   message never opens a segment.", right after the segment-start
   sentence.
2. Scope wording: NOTICE now reads "every durable fact from your
   thinking, tool calls, and steering messages since the segment
   start"; CUT_REQUEST reads "every durable fact from your work and
   from steering messages since the segment start" and adds "A
   steering message is a directive: keep it and follow it.";
   ROUND_REMINDER reads "Give kept context for the work and steering
   messages since the segment start first". "Steering messages"
   replaces the earlier draft "user messages" because mid-segment
   user-role records are exactly steers and the scaffold cut request,
   and the cut request text must not be archived as a durable fact.

No pinned phrase changed; `tests/test_segment_start_wording.py`
pins the segment rule, the steering scope phrase, and the directive
sentence too (8 tests).
