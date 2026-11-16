# Next
- Do not commit unless the user asks; the user chooses `wispy commit`, `wispy run`, or `wispy continue`.
- To recheck, run `python3 -m pytest wisp/tests wispy/tests -q` and `bash tests/test_wisp_sub_recipe.sh`.

# Open
- None.

# Cache
- `wisp/tests/test_attachments.py::TestChatGoldenBody::test_golden` fails before this ticket: GOLDEN expects the python3 description "Run a python3 command and return its output.", while TOOLS_SPEC at HEAD says "Run Python source and return its output." Commit ab2bcf6 changed the schema and left the pin. (From: wisp/tests/test_attachments.py:237, git show ab2bcf6) (Serves: Next)
- With that test deselected, 169 wisp tests pass; 97 wispy tests pass; `tests/test_wisp_sub_recipe.sh` passes 12 checks. (From: pytest runs, shell run) (Serves: Next)
- Opt-in rendering preserves the old block bytes except the deliberate law-sentence change; a diff shows only that line and no whitespace drift. (From: HEAD-rendered `--wisp` block, current `--wisp --wisp-subagents` block) (Serves: Next)

# Pointers
- Branch: main
- Session dir: /home/pnagyux/code/wisp/wisp-sessions/wisp-z33arb-001
- Ticket: /home/pnagyux/code/wisp/.tickets/wisp-z33arb/ticket.md
- Changed files: wisp/wisp, wispy/wispy, wisp/tests/test_subagent_laws.py, tests/test_wisp_sub_recipe.sh, md/design/skills.md
- Persona call with the new flag: wispy/wispy `PromptService.persona`.
- Rendered prompt commands: `wisp build-system-prompt --wisp` and `wisp build-system-prompt --wisp-subagents`.
