# Skills

A skill is one directory with a `SKILL.md` file. The file holds
frontmatter and a body. wisp finds skills, reads them, and puts their
bodies into a system prompt.

## What a skill file holds

```markdown
---
name: deploy
description: Ship one service to a test cluster.
---

The body. This text goes into the system prompt word for word.
```

`name` falls back to the directory name. `description` falls back to an
empty string. The parser handles plain, quoted, and block-scalar
values.

The body is the payload. wisp strips the frontmatter and carries no
other edit.

## Scan order

wisp scans these places, in this order:

1. The project scope. wisp walks from the current dir up to the git
   root, and checks `.wisp/skills`, `.agents/skills`, and
   `.claude/skills` in each dir. Outside a git repo, the walk stops at
   the current dir.
2. The user scope: `$HOME/.wisp/skills`, `$HOME/.agents/skills`,
   and `$HOME/.claude/skills`.
3. The XDG scope: `$XDG_CONFIG_HOME/skills`, then each dir in
   `$XDG_CONFIG_DIRS` plus `/skills`.
4. `WISP_SYSTEM_SKILLS`, split on `:`. Default: `$HOME/.agents/skills`.

### Shadowing

The first skill with a name wins. The scan order is the priority
order. A project-local skill shadows a user-level skill with the same
name.

A duplicate name warns on stderr and is dropped. That is not a silent
event on purpose. A name collision is a mistake in a repo.

A symlink is followed. The dedupe key is the physical path. A loop
cannot add a skill twice.

## The two views of a skill

| Command | Prints |
|---|---|
| `wisp skill ls` | One line per skill: name, description, path. |
| `wisp skill read NAME` | The body in a `<skill>` block. |

The block carries the name, the file path, and one sentence that says
which dir relative references use:

```text
<skill name="deploy" location="/repo/.agents/skills/deploy/SKILL.md">
References are relative to /repo/.agents/skills/deploy.

...body...
</skill>
```

The header exists because a skill often names a file next to it. The
model needs the base dir to resolve `scripts/run.sh`.

## Building a system prompt

`wisp build-system-prompt` joins blocks in a fixed order:

| Order | Block | Flag |
|---|---|---|
| 1 | The wisp block | `--wisp` |
| 2 | Every `AGENTS.md` in the chain | `--agents-md` |
| 3 | The skill catalog: one line per skill | `--skills` |
| 4 | Stdin, wrapped as one block | always, when stdin is not a tty |

The order is not arbitrary. Later text carries more weight in most
models. The deepest, most local instruction sits last, and the stdin
block sits after it.

The catalog is a list of names, not bodies. A body enters the prompt
only when the caller names the skill and reads it.

That split is the point. A catalog of 50 skills costs 50 lines. A
prompt with 50 bodies costs more than the session.

## No skills ship with the tools

The repository holds no skill. A skill belongs to the project it
serves. Two projects can hold two skills with the same name, and each
one shadows the other in its own tree.

`wispy --skills` reads the same scan order. The names are resolved
once, at session start, and saved in the ticket dir.
