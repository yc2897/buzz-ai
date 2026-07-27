# Agent skills

The catalogue of skills the five agents can invoke. This file is the single source of
truth: it ships into the container at `/opt/buzz-skills/README.md`, so the agents can read
it too. Adding a skill means editing here and in `run-agent.sh` — never the prompts.

## What each skill is for

| Skill | Reach for it when |
|---|---|
| `grilling` | The idea is still forming. Interview the owner one question at a time, resolving one decision before moving to the next. Don't deliver a verdict until you actually understand the thing. |
| `handoff` | A conversation has reached a conclusion the owner will act on somewhere else. Writes the brief they carry out to a coding agent on their own machine. |
| `to-tickets` | A plan is agreed and needs sequencing — vertical slices, each declaring what blocks it, written one file per ticket. |
| `to-questionnaire` | Answering properly needs information only a third party holds: a recruiter, a hiring manager, a vendor, a colleague. |
| `research` | A question deserves primary sources and a written, cited answer rather than a chat reply. |

Everything a skill writes goes under your working directory (`/home/agent/work/<ROLE>`),
into `handoffs/`, `tickets/`, `research/` or `questionnaires/`. **Always report the path in
chat** — the owner reads those files from their own machine, and it's the only way your
work leaves this container.

## Which agent gets what

| Skill | Career | Operations | Knowledge | Red Team | Engineering |
|---|:-:|:-:|:-:|:-:|:-:|
| `grilling` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `handoff` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `to-tickets` | | ✓ | | | ✓ |
| `to-questionnaire` | ✓ | ✓ | | | |
| `research` | | | ✓ | | |

## Adding or changing a skill

1. Drop the skill folder in here (`SKILL.md` + `agents/openai.yaml`).
2. Add it to the relevant roles' `SKILLS=` lists in `run-agent.sh`.
3. Add a row to both tables above.
4. Rebuild.

**You should not need to touch `prompts/`.** A skill's `description:` is injected into the
agent every turn automatically, so listing skills in a prompt is duplication that goes
stale. Only put something in a prompt when it's a judgement the generic description can't
carry — e.g. Red Team's rule for choosing between `grilling` and its ranked-objections
method, which depends on that role's mission rather than on the skill.

Resident cost is frontmatter only; bodies load on trigger. Roughly 125–265 tokens per
agent today. Keep it that way — anything added here is paid on *every* turn, forever.

## Why these five and not the other 36

Upstream is written for a developer in an IDE with a repo and an issue tracker. These
agents are a **clinic**, not an operating theatre — they consult, and the building happens
later in Claude Code on the owner's machine. So the surgical skills (`tdd`,
`diagnosing-bugs`, `prototype`, `code-review`) are deliberately absent even though they're
good; they'd fire in a room with no patient on the table. Superpowers was considered for
Engineering and rejected for the same reason, at 10× the resident cost.

Two upstream facts rule most of the rest out: 24 of the 41 skills are
`disable-model-invocation: true` (slash-command only, and Buzz has no slash UI), and many
of the remainder need a git repo or a GitHub issue tracker to do anything.

## Where these came from

[mattpocock/skills](https://github.com/mattpocock/skills), MIT licensed (see
`LICENSE.mattpocock`). Vendored at commit `ed37663` (2026-07-21) rather than installed from
a marketplace, so a build is reproducible, needs no network, and can't change under you.

Each folder works for **both** runtimes unchanged: `SKILL.md` is read by Claude Code, and
`agents/openai.yaml` by Codex. `run-agent.sh` copies the per-role subset into
`$CLAUDE_CONFIG_DIR/skills/` or `$CODEX_HOME/skills/` at start.

## Local modifications

These are forks, not copies. Re-pulling upstream will silently undo all of it.

**All of `handoff`, `to-tickets`, `to-questionnaire`** — removed
`disable-model-invocation: true` from `SKILL.md` and the `policy.allow_implicit_invocation:
false` block from `agents/openai.yaml`. Upstream gates these because it expects you to type
`/handoff` in an IDE. Buzz delivers plain chat text, so with the gate in place they could
never fire at all. Removing it restores the intended behaviour via natural language.

That removal has a catch worth remembering if you ever vendor another gated skill:
**a gated skill's description is written as a label, not as a trigger**, because the slash
command *was* the trigger. Ungating one without giving the model something to match on
produces a skill that is technically live and never fires. So `handoff` and
`to-questionnaire` also got a `Use when …` clause appended to their descriptions. Compare
`grilling`, which shipped with one because it was model-invocable upstream.

**`handoff`** — wrote to the OS temp directory, which this container wipes on the nightly
backup restart. Now writes to `handoffs/<date>-<slug>.md` in the agent's working directory.
Also told it that its reader is a coding agent in a repo it cannot see.

**`to-tickets`** — dropped the `/setup-matt-pocock-skills` tracker bootstrap (that slash
command can't run here) and pinned it to the local-files path it already supported. Output
moved from `.scratch/<slug>/issues/` to `tickets/<slug>/` so the files are visible in a
plain file browser. Removed the now-dead GitHub `<issue-template>`, and told it to name its
assumptions rather than guess at code it can't read.

**`research`** — upstream opens with "spin up a background agent", which fails closed if
sub-agent dispatch isn't available through the ACP adapter. Now degrades to inline. Added a
verified-vs-inferred split, and a fixed output path.

**`grilling`** — unmodified.
