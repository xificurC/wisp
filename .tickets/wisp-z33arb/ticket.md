---
id: 'wisp-z33arb'
name: 'subagent system prompt under --wisp-subagents'
status: 'closed'
created: '2026-11-16T10:36:49Z'
parent: null
blocked-on: []
---

## Decision

- `--wisp` now emits the wisp block without the `SUBAGENTS` section.
- `--wisp-subagents` adds the `SUBAGENTS` section inside the same
  `<wisp>` block and implies `--wisp`.
- `wispy` passes both flags, so its sessions keep the subagent laws.
- The no-block law now tells the session to rebuild its prompt with
  `--wisp-subagents`.
