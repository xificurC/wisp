# Next
- No task pends: the ticket is closed and verified. Open a new ticket for further vision or image work.

# Open

# Cache
- `wisp.modelcfg` is rewritten at every run start from the model-info file named by `WISP_LLM_MODEL_INFO_FILE`, so a `vision` declaration change applies on the next run of the same session; the live drill continued a poisoned session at rc 0 with no new session. (From: wisp/wisp `refresh_model_cfg`; ticket Verification record) (Serves: cold)

# Pointers
- Ticket: /home/pnagyux/code/wisp/.tickets/wisp-ekffsc/ticket.md (closed; Plan item 3 and the wire-placeholder Verification record hold the design and live proof)
- Code: /home/pnagyux/code/wisp/wisp/wisp (`vision_enabled_of`, `text_only_parts`, `message_of`, `chat_image_message`, `items_of_responses`, `items_of_anthropic`, `body_of_chat`, `body_of_responses`, `body_of_anthropic`, `_run_load_image`, the `--attach` gate)
- Tests: /home/pnagyux/code/wisp/wisp/tests/test_vision_gate.py (23 tests), /home/pnagyux/code/wisp/wisp/tests/test_providers.py
- Live drill: /home/pnagyux/code/wisp/wisp-sessions/live-check/ekffsc-wire-env, with models-glm-text.json and red.png in the same directory
- Working tree: /home/pnagyux/code/wisp, uncommitted edits from this ticket and other tickets; no commit made
