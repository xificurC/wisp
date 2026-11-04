# tikit

`tikit` is a ticket store in one file. One ticket is one Markdown file
with YAML frontmatter. Nothing else is required: no daemon, no database,
no index.

## The ticket model

A ticket is a name, a status, a creation time, and an optional parent.
Everything else is free.

| Field | Kind | Meaning |
|---|---|---|
| `id` | string | The identity. Also the dir name. |
| `name` | string | One line that a human can scan. |
| `status` | string | The state of the work. |
| `created` | string | ISO time, UTC. |
| `parent` | id or null | The ticket this one belongs to. |
| `blocked-on` | list of ids | The tickets that must close first. |

Any other key is legal. A project adds `owner`, `priority`, or a URL.

The tool does not enforce the status set. The convention that the tools
around it use:

```text
open | wip | closed | withdrawn | blocked
```

A status outside the set is not an error. It is a name that no gate
knows.

## The id

The id is four characters from the current dir name, a dash, and six
random lowercase letters or digits: `wisp-ab12cd`.

The dir name keeps its case. The random part comes from `/dev/urandom`.
`--id` overrides it.

A readable id is not a goal. The name carries the meaning. The id must
only be unique and cheap.

## create writes frontmatter only

`tikit create` writes the six fields and no body. It writes no heading.

The reason: a heading is content. A heading says "Decisions" and then
holds nothing. The first session then either fills it with filler or
deletes it. Both cost a turn.

An empty body is honest. It says the work has not started. The first
session writes the structure that its work needs.

The tool never rewrites the body. The body belongs to the worker.

## Three query modes

| Mode | Gives | For |
|---|---|---|
| `--files` | One absolute path per ticket | A shell loop, and `wispy` binding |
| `--json` | One JSON object per line | A pipe into `jq` |
| `--sql <query>` | Rows from a table named `tickets` | A report, and a join |

The path is the default. It is the unit that every other tool takes: a
session dir binds to a ticket path, not to an id.

### Filters

`--key value` keeps a ticket whose key matches the value as a regex.
`not` inverts the next filter. Filters compose with AND.

A missing key fails a positive filter and passes a negated one. That is
the useful reading: `--not --status closed` keeps a ticket that has no
status, because it is not closed.

A list value matches as `:a:b:`. The colon form makes a list query the
same as a scalar query.

Filters do not mix with `--sql`. The query language already has a
negation, and two ways to express one filter invite a bug.

### The SQL table

`--sql` builds an in-memory table from the frontmatter. The columns are
`id`, `_body`, `data`, and one TEXT column per key seen.

`data` holds the whole frontmatter as a JSON object. So both forms work:

```sql
SELECT id FROM tickets WHERE status = 'open';
SELECT id FROM tickets WHERE json_extract(data, '$.status') = 'open';
```

The table is built per call. There is no file to keep in sync and no
schema to migrate.

## Why one file per ticket

- A diff is readable. A reviewer sees the change to the record.
- A conflict is local. Two tickets cannot conflict.
- A delete is a file delete.
- `git` stores it; no export step exists.

The body is prose the worker writes. A ticket is not a row in a
tracking system. It is the work product.

## What the tool does not do

- It does not run a workflow. The phases belong to `wispy`.
- It does not write headings. The worker writes the body.
- It does not validate a status. The gate belongs to the caller.
- It does not edit a ticket. Edit the file with your editor.
