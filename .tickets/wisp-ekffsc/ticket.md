---
id: 'wisp-ekffsc'
name: 'wisp vision gate and wispy demote recovery'
status: 'closed'
created: '2026-11-18T13:50:02Z'
parent: null
blocked-on: []
---

## Findings

The stuck chain, confirmed in the code:

1. `Tools._run_load_image` (wisp/wisp, line 3621) reads the file,
   sets `record["attachments"]`, exit 0. The round commits to
   wisp.jsonl with the image bytes inside the tool record.
2. The next request replays the record. `body_of_chat` (line 4441)
   collects tool attachments into `pending_images` and
   `chat_image_message` (line 4466) sends them as `image_url` data
   URIs. The responses and anthropic builders do the same.
3. A text-only endpoint (GLM 5.3 through the company LiteLLM server)
   answers HTTP 400. `sse_stream` logs `http_error`, the HttpError
   unwinds to main, and the run exits 77 (`kind=http`).
4. wispy `decide_after_work` (wispy/wispy, line 433) maps rc 77 with
   finished work to `("stop", 77)`, so it starts a distill in the same
   session. The distill request replays the same attachments, hits the
   same 400, exits 77. `.phase` stays `distill`, and every
   `wispy continue` retries the distill on the same poisoned session:
   the loop never escapes.
5. Even a bare `wisp continue` on the session is stuck the same way:
   every request rebuild carries the image parts.

Root cause: nothing tells `load_image` the run's endpoint takes no
image content. The tool succeeds locally, poisons the stored
conversation, and every later request dies on the replay.

wisp knows per-model facts only through `wisp.modelcfg`
(MODELCFG_FIELDS, line 2075: context, input, output, cacheRead,
cacheWrite) filled from `WISP_LLM_MODEL_INFO_FILE`. No field says
whether a model takes images.

## Plan

Settled unit of work: keep image content out of conversations the
endpoint rejects, and add one generic recovery in wispy for sessions
whose conversation no run can replay. The user rejected the strip
command (2026-11-19): a run may fail in many ways, so the repair is
generic and lives in wispy, not in wisp.

1. wispy demote (generic recovery). Done. New `wispy demote` command:
   it demotes the session named by the open .phase (work or distill,
   never commit), saves its response under responses/, records it in
   sessions.txt, clears .phase, then starts a fresh work session with
   the same skills, under the same session cap accounting as wispy
   run. The first turn of the successor carries a recovery note that
   names the demoted session dir and, when stdin holds one, the
   reason. The demoted conversation is never replayed; its transcript
   stays readable on disk. The repair is generic: it escapes any
   session whose requests keep failing, whatever the cause.
2. Vision capability. Done. `wisp.modelcfg` entries gain a `vision`
   boolean; `model_table_ok_of` accepts it. Resolution order in
   `vision_enabled_of`: `WISP_LLM_VISION` env (on/off words, like
   WISP_LLM_STREAM), then the modelcfg `vision` field, then default
   on, so vision models keep working with no config.
3. Wire placeholder. Done (2026-11-19, settled with the user). The
   tool-time gate is reverted: `_run_load_image` always stores the
   image. One helper, `text_only_parts`, runs in the builders:
   `message_of` and `chat_image_message` for openai-chat,
   `items_of_responses`, and `items_of_anthropic`. Vision off
   replaces each image part with the pi placeholder text - "(image
   omitted: model does not support images)" on a user record,
   "(tool image omitted: model does not support images)" on a tool
   record - so the request stays text-only. `body_of_chat`,
   `body_of_responses` and `body_of_anthropic` read
   `vision_enabled_of` once and pass the boolean down. Stored records
   keep their bytes, so declaring a model non-image repairs a
   poisoned session in place, and a later run with vision on replays
   the real image with no repair step.
4. Attach gate. Kept. `wisp run --attach` with vision off still fails
   at start with VISION_OFF_NOTE, before the prompt is read, like the
   request checks in `check_request_of`. The gate guards new input
   before any bytes are stored, so it cannot poison; the wire
   placeholder covers the stored history, which is the poisoning
   case.
5. wispy mapping. Done. `decide_after_work` maps wisp rc 77 to the
   `api` action (exit 1, keep work, repair note), not to a distill
   attempt: a distill in a session whose work run died on an endpoint
   error replays the same error. The api note and the
   distill-failure note name `wispy demote` as the repair when
   retrying the same session does not escape.
6. Tests. Done. wisp/tests/test_vision_gate.py (23 tests): vision
   resolution over env, modelcfg and the table shape; load_image
   stores the image under every vision setting; each builder replaces
   image parts with the right placeholder; vision on keeps the wire
   image; build_request reads the modelcfg field; the stored record
   keeps its bytes. wisp/tests/test_providers.py `_Fs` gains `exists`,
   because build_request now reads wisp.modelcfg. wispy tests
   unchanged: rc 77 maps to api; demote replaces the phase session on
   work and distill phases, refuses commit and no-marker, carries the
   reason, keeps the skills.

Verification: pytest wisp/tests wispy/tests, plus one live run on the
company LiteLLM server with GLM 5.3 calling load_image under a
vision-off setting, and one poisoned session escaped through
`wispy demote`.

Verification record (2026-11-19):

- pytest wisp/tests wispy/tests: 338 passed, 8 failed. All 8 failures
  predate this ticket's edits: test_attachments test_golden is red at
  pristine HEAD (the pinned body holds an old python3 tool
  description); test_attachments TestRenderMarker x2,
  TestToolRecordWire replay, test_steer ReplayTest x2, and
  test_subagent_laws test_docstring_mandate fail on uncommitted
  changes other tickets left in the shared tree (records_to_stream
  signature, docstring command list); wispy PromptFileTests
  test_the_commit_runs_no_check fails on a line wrap another ticket
  left in prompts/commit-rules.md. New: wisp/tests/test_vision_gate.py
  15 passed; wispy DemoteTests 7 passed plus the rc 77 api test.
- tests/test_wisp_*.sh: all seven scripts PASS with fail=0.
  tests/*.py: all three print PASS.
- Live, GLM 5.3 on the company LiteLLM server: WISP_LLM_VISION=off
  and a WISP_LLM_MODEL_INFO_FILE table with vision: false each
  degrade load_image to the text refusal and the run exits 0
  (sessions ekffsc-gate-env, ekffsc-gate-cfg). The refusal behavior
  is superseded by the wire-placeholder change below: load_image now
  stores the image in both cases.
- Live poison drill: with no vision config, load_image commits image
  bytes, the next request answers HTTP 400 (not a multimodal model),
  the run exits 77 and wisp continue exits 77 again (session
  ekffsc-poison). A scratch ticket whose .phase named that session
  escaped through `wispy demote`: the poisoned session was recorded
  and demoted, the successor work session ran to completion on the
  same endpoint, the distill wrote STATE.md, wispy exited 0
  (successor session ekffsc-demote-002, scratch ticket removed after
  the drill).
- AI_SETUP_RECIPES.md updated per the user's condition: WISP_LLM_VISION
  row in the env table, the vision field documented in the model-info
  section, vision added to the litellm and openrouter jq recipes, the
  opencode-go by-hand note, and the check-one-model vision query.

Verification record (2026-11-19, wire-placeholder change):

- pytest wisp/tests wispy/tests: 331 passed, 8 failed. The 8 are the same
  pre-existing failures listed above; no new failure. wisp/tests/
  test_vision_gate.py: 23 passed. wisp/tests/test_providers.py: 35 passed
  after its `_Fs` fake gained `exists`.
- tests/test_wisp_*.sh: all seven scripts PASS, fail=0. tests/*.py: all
  three print PASS.
- Live, GLM 5.3 on the company LiteLLM server, session
  wisp-sessions/live-check/ekffsc-wire-env: the model called load_image
  under WISP_LLM_VISION=off, the tool stored the image, the run exited 0,
  and the model quoted the placeholder back ("(tool image omitted: model
  does not support images)").
- Live poison-repair drill on the same session: with no vision setting
  the next `wisp run` replayed the stored image, the endpoint answered
  HTTP 400 (the deployment is not a multimodal model), and the run
  exited 77. Setting `vision: false` for GLM 5.3 in the model-info file
  (no env) and running `wisp continue` exited 0 on the same session; the
  image stays in wisp.jsonl (100 base64 bytes) and the request carried
  the placeholder instead.
- AI_SETUP_RECIPES.md and the wisp help text and docstrings reworded:
  vision off keeps image parts off the request wire, load_image always
  stores the image, and --attach still refuses at start.

## Out of Scope

- No retry-without-images inside a failed request (self-healing on a
  400 that mentions images). The wire placeholder is not a retry: it
  follows the vision setting on every request, including the replay
  of a stored image. A mid-run auto-strip can come later as its own
  ticket.
- No OCR, no image description service, no vision-model routing.
- No change to the providers' image wire formats themselves.

## Gaps

- Vision default with no modelcfg entry: settled as allow (default
  on). The user approved the plan shape (2026-11-19), and as of the
  wire-placeholder change the residual risk is one failed run: declare
  the model non-image, then the same session continues, because the
  stored bytes stay and the next request replaces them with the
  placeholder (live-proved, session ekffsc-wire-env). `wispy demote`
  stays the generic backstop. The safe default (deny) is still not
  needed to protect the loop.
- Strip-retry (runtime vision learning): proposed to the user
  (2026-11-19, session wisp-ekffsc-003), rejected 2026-11-19 in favor
  of the wire placeholder; the error-as-tool-response evaluation (last
  Gaps entry, 2026-11-19) also recommends against it as the recovery
  layer. Design,
  verified against the code: `Llm.turn` (wisp/wisp, line 4021) catches
  HttpError status 400; when the conversation holds attachments and
  vision is not learned off, it sets a world flag `vision_learned_off`,
  rebuilds the request without image parts, and retries once in the
  same turn. A second failure re-raises the original error, so rc 77
  and the wispy api/demote backstops stay. `vision_enabled_of` gains
  the flag as a resolution step, so the existing tool-time gate, the
  --attach gate, and the three body builders pick it up with no new
  code path: later load_image calls degrade to the existing refusal,
  which is the behavior the user asked for. The builder appends a
  wire-only suffix to tool records that carry attachments (the image
  was not delivered), the steer-tag pattern in `user_text_of`; stored
  records stay untouched. No error-text sniffing: the retry is the
  test. Persistence across runs is dropped: `refresh_model_cfg`
  (wisp/wisp, line 3528) overwrites the session's wisp.modelcfg from
  WISP_LLM_MODEL_INFO_FILE every run, so that file is not a durable
  target; an unconfigured text-only model pays one 400 per run, at
  the learning round. Open decisions: (a) new ticket or added unit
  here, since the Out of Scope line below reserves it; (b) trigger:
  any 400 on an image-bearing request (recommended, provider-neutral)
  vs error-text sniffing; (c) WISP_LLM_VISION=on: the learned flag
  wins (recommended, the endpoint 400 is a fact) vs the env vetoing
  the rescue.

- Capabilities API scouting (2026-11-19, live probes, no code change;
  the user set the client-side query aside as too specific on
  2026-11-19, and the same evaluation recommends against wiring it
  into vision_enabled_of):
  - Company LiteLLM proxy: `GET /model/info` (base URL of the chat
    endpoint, same bearer key) returns one entry per deployment with
    `model_info.supports_vision` (true / false / null). Live check:
    34 entries, 25 true, 4 false, 5 null. `GET /v1/models` (OpenAI
    standard) on the same server carries only ids and token limits,
    no capability fields.
  - GLM 5.3, the poison model of this ticket: `supports_vision` is
    null. Its backend is a custom `hosted_vllm` deployment; LiteLLM
    leaves vision undeclared for such deployments unless a server
    admin declares it. The 4 false and 25 true entries prove the
    declaration pipeline exists (db_model entries, editable
    server-side). The field is an admin declaration, not measured
    truth: a wrong declaration lies in either direction.
  - Other providers: OpenRouter `GET /api/v1/models` (public) returns
    `architecture.input_modalities` per model (Qwen 3 32B is
    text-only, gemini models list image). OpenAI and Anthropic
    model-list endpoints return ids and display names only, no
    capability fields.
  - Implication for the strip-retry decision: a client-side
    capabilities query could feed `vision_enabled_of` as a resolution
    step (env > modelcfg > server answer > default on) when the
    endpoint answers `/model/info`; true and false are trusted, null
    falls through to the default. That removes sniffing for every
    model the server declares, but GLM 5.3 stays null until a
    server-side declaration exists, so strip-retry (or the modelcfg
    file) remains the backstop for undeclared deployments. A single
    server-side declaration of GLM 5.3 fixes the original poison case
    with zero wisp code. The user's stated risk stands for
    strip-retry: a 400 from a wrong image format (model does take
    images) would be masked as vision-off; the capabilities query
    separates the two cases for declared models.

- Error-as-tool-response stop (2026-11-19, evaluated, no code change): the
  user's proposed recovery, evaluated against the code. On an HttpError
  4xx from a request whose loaded records hold attachments, rewrite those
  records — drop `attachments`, make the tool content the delivery
  failure (raw server text plus the file path and local-result facts,
  exit nonzero), rewrite wisp.jsonl, stop the run. The next run or
  `wisp continue` replays a text-only conversation and the model reads
  the degraded tool response. Verdict: sound, simpler than strip-retry,
  recommended over strip-retry and over the /model/info query as the
  recovery layer; the modelcfg `vision: false` entry stays the long-term
  layer, `wispy demote` stays the generic backstop. Why it fixes the
  unrecoverability: request bodies are a pure function of the stored
  records — load_events reloads all of wisp.jsonl every run, and
  body_of_chat (pending_images, wisp/wisp line 4519), items_of_anthropic,
  and the responses builder turn every attachments field into image
  parts — so a new prompt never escapes the replayed image; rewriting
  the record is the one layer all three builders share. No cross-run
  state, so no refresh_model_cfg overwrite problem and no masked
  wrong-format 400: each delivery failure is recorded per call, the
  source file stays on disk, and the model can re-call load_image or
  inspect with bash. Issues found, all manageable: (a) the attachment
  record is already committed at the round boundary (loop_rounds flushes
  right after tools.execute) and flush_records appends only past the
  commit point, so rewriting the in-memory dict persists nothing; the
  rewrite must edit committed wisp.jsonl lines — precedent:
  _reload_committed already rewrites the log when dropping a partial
  tail; run the rewrite inside commit_guard and write one wisp.log
  degraded line per record, so the edit is never silent. (b) Trigger:
  status 400-499 while any loaded record holds attachments, no
  error-text sniffing; misattribution is one-shot and honest — the raw
  server text is quoted, the next request holds no images so the
  trigger cannot fire again, plain rc 77 and the wispy api/demote
  backstop still apply; keep the original local result facts in the
  rewritten text so the model can recover. (c) `wisp run --attach`
  attachments ride the user record (run_agent_loop, line 1177): the
  rewrite must cover user records too — strip the attachments key,
  append the delivery note to the record text, prompt text untouched —
  or the --attach poison path stays open when vision is unconfigured.
  (d) Exit 77, not 0, with the error line extended ("N image records
  degraded; wisp continue to proceed"): the turn did fail, rc 0 would
  send wispy straight into a distill of a turn with no assistant reply,
  and with the rc 77 to api mapping already shipped the retry the note
  asks for now succeeds. (e) The stop costs one extra run lifecycle:
  the model reacts on the next run, not inside the failing one — the
  user's stated shape, recorded so it stays a choice. Open decisions:
  trigger statuses (400 only vs any 4xx); rc 77 vs 0; user-record
  rewrite for --attach; new ticket or a unit here — the Out of Scope
  "mid-run auto-strip can come later" line needs amending either way,
  since this design strips without retrying. Settled 2026-11-19: not
  built. The wire placeholder plus a modelcfg declaration recover the
  same session in place, which is the user's chosen shape.

- pi inspection (2026-11-19, read-only, ~/code/pi at 5f89cc0a7; no
  code change). pi (earendil-works/pi) hits the same problem one layer
  above the tool: the tool always records the image, and each request
  builder substitutes an honest placeholder when the selected model's
  declared `input` lacks "image".
  - Declaration: every model carries `input: ("text" | "image")[]`
    (packages/ai/src/providers/model-schema.ts:11, 101-108). Built-in
    entries come from models.dev `modalities.input`
    (catalog/sources/models-dev.ts:184-190). A custom `models.json`
    entry defaults to `["text"]`
    (packages/coding-agent/docs/models-configuration.md:38), so an
    undeclared proxy model counts as text-only.
  - Wire downgrade: `transformMessages` ->
    `downgradeUnsupportedImages`
    (packages/ai/src/api/transform-messages.ts:60-101) rewrites image
    blocks of user and toolResult messages into the texts "(image
    omitted: model does not support images)" and "(tool image omitted:
    model does not support images)". All six builders call it
    (openai-completions:1219, openai-responses-shared:226,
    anthropic-messages:1434, bedrock-converse-stream:1027,
    google-shared:202, mistral-conversations:144). The user setting
    `images.blockImages` adds a second, model-independent placeholder
    "Image reading is disabled." (coding-agent/src/core/sdk.ts:296-329).
  - The tool keeps the fact: `read` always returns the text note plus
    the image block (coding-agent/src/core/tools/read.ts:284-295), also
    for a text-only model. The capability fact travels as a UI-only
    detail `imageUnsupportedByModel`, and the TUI prints "[<model> does
    not support images; it saw a placeholder instead]"
    (read.ts:40-47, tools/renderers/read.ts:118-120). The test names the
    rule: "should always read images (filtering happens at convertToLlm
    layer)" (test/block-images.test.ts:73).
  - Storing the verdict was a pi bug and got reverted: CHANGELOG #12131
    (coding-agent/CHANGELOG.md:21) "Fixed `read` storing a note that
    the current model does not support images, which was replayed to
    the model as stale text after switching to a vision model." The
    placeholder is per request; the record stays model-neutral.
  - No error sniffing, no strip-retry, no capability query: the
    provider retry policy covers 408/409/429/5xx only
    (packages/ai/src/utils/provider-retry.ts:30-36), so a 400 reaches
    the user. The recovery is switching to a model that declares image
    input; history still holds the image, so the switch works.
  - History is append-only: a `context_edit` entry omits an earlier
    entry from model context or replaces only its content, while raw
    history, usage, and UI history stay untouched
    (coding-agent/src/core/session-manager.ts:170-180, 1370-1410;
    docs/session-format.md:235). Overflow recovery uses it, and
    extensions may propose it.
  - Reading for wisp: (1) the wire placeholder answers the user's
    "dropping the attachments is a lie" objection and keeps history
    intact; (2) the shipped tool-time gate stores a capability verdict
    that goes stale under WISP_LLM_VISION=on or a modelcfg change —
    the bug pi fixed in #12131 — and it destroys image bytes a later
    vision-on run could send; (3) the shipped --attach refusal has no
    pi counterpart, because pi accepts the attachment and downgrades at
    the wire; (4) pi confirms two decided points: static declaration
    over a live /model/info query, and no error-text sniffing; (5) if
    the error-as-tool-response design is chosen, pi's append-only
    `context_edit` (targetId plus replacement or null) is the shape to
    copy instead of editing committed wisp.jsonl lines; (6) pi escapes
    a mis-declared model by switching models, which wisp cannot do
    mid-session, so wisp still needs the demote backstop.
  - Port walkthrough (2026-11-19, session wisp-ekffsc-007, read-only):
    a pseudo-session over the verified source confirmed the recovery
    property end to end: turn 1 stores the image and sends the
    placeholder, turn 2 replays both reads as placeholders and the
    request succeeds on the same session, a `/model` switch sends the
    stored bytes for real with no repair step. The port is one change
    set: revert the shipped tool-time gate so `load_image` always
    stores the image, add the shared wire helper in the builders,
    settle open decision (b) for `--attach`. Two mechanisms do not
    port: pi switches models mid-session and wisp cannot; pi defaults
    custom models to text-only and wisp defaults vision on, so the
    unconfigured GLM 5.3 case keeps its 400. One new fact for the
    port: a successor wisp session on a vision-capable model replays
    the stored image bytes unchanged, because request bodies are a
    pure function of the stored records — wisp needs no
    image-recovery mechanism, only a model choice, and a model choice
    means a new session.
  - Open decisions: settled 2026-11-19 (session wisp-ekffsc-009) by the
    user's instruction: "declare the model non-image and after the fix
    wisp will have the image in history but not send it over the wire."
    (a) gate point: the wire-only placeholder with `load_image` always
    storing the image (pi's shape) - shipped. (b) `--attach`: the
    start-time refusal stays; it guards new input before any bytes are
    stored and cannot poison, while the wire placeholder covers stored
    history, which is the poisoning case. (c) the mis-declared text-only
    model (GLM 5.3 with no modelcfg entry): no error-as-tool-response
    stop and no strip-retry; declaring the model non-image repairs the
    same session in place (live-proved, session ekffsc-wire-env), and
    `wispy demote` stays the generic backstop. The default-on vision
    resolution stays: pi can default a custom model to text-only because
    the placeholder keeps every request valid, and wisp has no per-model
    catalog, so text-only by default would disable vision for every
    unconfigured vision model.

- Misconfigured image declaration in pi (2026-11-19, read-only model of the
  400 path; no code change). Scenario: a model entry declares image input but
  the deployment rejects images. The declaration can come from a models.json
  `models` entry (`input: ["text","image"]`, models-configuration.md:38), a
  `modelOverrides` entry (models-configuration.md:68), or the built-in catalog.
  pi keeps no second opinion to compare against: no capability probe, no error
  sniffing, no learned image flag.
  - Trace. (1) `read` returns the text note plus the image block and consults
    `ctx.model.input` only to set a UI-only detail, so a declaring model gets
    no hint (tools/read.ts:284-295, 40-47). (2) The tool result is appended to
    the context before the next request (agent-loop.ts:270-283). (3) The next
    request runs `transformMessages`; `downgradeUnsupportedImages` returns the
    transcript untouched because `model.input.includes("image")`
    (transform-messages.ts:62-64), so the builder emits real image parts:
    openai-completions moves tool-result images into a user message with
    `image_url` data URLs (openai-completions.ts:1429-1460); anthropic puts
    them inside the tool_result block (anthropic-messages.ts:1766-1789).
    (4) HTTP 400. `retryProviderRequest` retries 408/409/429/5xx only
    (provider-retry.ts:30-36), so no transport retry. The builder turns the
    error into an AssistantMessage with stopReason "error" and
    `"<status>: <body>"` as errorMessage (openai-completions.ts:695-710,
    error-body.ts:78-88). Auto-retry classifies by error text, 400 matches no
    retryable pattern (utils/retry.ts:37-47, 285-287), so no backoff attempt
    either. (5) The loop ends the run on an error message
    (agent-loop.ts:254-262); the session appends the error message, and the
    image stays in its tool result. (6) The TUI prints `Error: 400: ...`
    (assistant-message.ts:258-261) and, since the error is non-retryable,
    suggests `/bug` (interactive-mode.ts:2313-2318). `pi -p` exits 1
    (print-mode.ts:154-158); `--mode json` leaves the exit code at 0.
    (7) The next prompt rebuilds the same body and 400s again. Error assistant
    messages are skipped at the wire (transform-messages.ts:216-223), so the
    image is the only poison and the session stays stuck while the declaration
    stays wrong.
  - Escapes, all user-driven and all keeping the image in history: `/model`
    to a model that declares text-only (the placeholder path, the shipped
    design); fix `input` in models.json or modelOverrides and re-select the
    model (a session replacement re-reads models.json through
    createAgentSessionServices -> ModelRuntime.create -> ModelConfig.load;
    `/reload` does not, slash-commands.md:28 and agent-session.reload);
    `/tree` to an entry before the read or `/fork` from an earlier user
    message, which drops the branch from the projected context but keeps it on
    disk; `/new`, which loses the context.
  - What does not escape: compaction. `/compact` in a short session refuses
    because the cut point keeps ~20k recent tokens and nothing precedes it
    (settings-defaults.ts:9-13, compaction.ts:431-500, 901). Threshold
    compaction cannot trigger either, because the failed turns add almost no
    tokens. In a long session threshold compaction can drop an older image,
    and the summary request is text-only by construction
    (compaction.ts:721-742, compaction/utils.ts:121-156), so compaction
    neither 400s nor reliably heals.
  - pi's one request-level 400 downgrade is unrelated: Anthropic strict-tool
    limits, matched by error text, retried once before the stream starts, the
    session marked in an in-memory keyed set cleared at session end
    (anthropic-messages.ts:917-940, strict-tool-limits.ts). No image
    equivalent exists; the pattern (pre-stream 400 catch, rebuild, one retry,
    per-session learned flag) is pi's own precedent for the strip-retry shape
    the ticket's Gaps entry designs.
  - Silent variant: a deployment that returns 200 and ignores image parts
    produces no error and no local hint, because the declaration says image.
    Detection is impossible client-side, and only a model switch or a
    declaration fix changes behavior. Reverse misdeclaration (declares text,
    takes images) is silent the other way: the placeholder is sent and the TUI
    prints "[<model> does not support images; it saw a placeholder instead]"
    (renderers/read.ts:118-120); a declaration fix plus a re-selected model
    replays the stored bytes.
  - Anthropic placement variant: images inside a tool_result are legal for
    Anthropic (anthropic-messages.ts:1766-1789); a proxy that accepts user
    images but rejects tool_result images 400s on every successful read. The
    escapes are a model switch or an `api` change to openai-completions, which
    moves tool images to a user message (openai-completions.ts:1445-1460).
  - Reading for wisp: the pi shape does not cover this case either. With the
    wire placeholder a misdeclared model still receives the image and still
    400s; the placeholder only rescues under-declared models. So port open
    decision (a) is unchanged by this scenario, and the wire placeholder adds
    exactly one recovery the shipped tool-time gate destroys: the stored bytes
    stay replayable under a modelcfg fix or a model switch. The misdeclared
    case keeps wisp's rc 77 -> wispy api -> demote backstop, which is stronger
    than pi's manual `/model` and `/tree`, because one command replaces the
    poisoned session.
