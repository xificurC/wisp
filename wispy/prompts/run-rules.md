# Session rules

These rules hold in the work session. The user turn can carry another rule
file. That file takes priority.

- The ticket is the contract. Its Out of Scope section binds.
- The system prompt names the ticket file. Edit that file with your tools
  when you settle a record, a decision, or a task tick. Your reply is not
  the ticket. wispy does not copy a reply into it.
- wispy sets the status to `wip` when the work starts. Keep the rest of the
  frontmatter as it is. A settlement may set the status to `closed`.
- The state file is the handoff for the next session. wispy writes it from
  your reply at the distill. Do not edit it here.
- A loaded skill stays loaded. Do not restate a skill body.
- Verify the state note against the files before you use it. It is working
  memory, not truth.
- Do the next unit of work. Stop when the request is done, when the ticket
  tasks are done, or when a gap needs a decision from the user.
- Do not plan a commit. If the user did not explicitly request you to
  commit, don't.
