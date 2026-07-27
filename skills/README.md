# Vendored agent skills

Five skills from [mattpocock/skills](https://github.com/mattpocock/skills), MIT licensed
(see `LICENSE.mattpocock`). Vendored at commit `ed37663` (2026-07-21) rather than installed
from a marketplace, so a build is reproducible, needs no network, and can't change under you.

Each folder works for **both** runtimes unchanged: `SKILL.md` is read by Claude Code, and
`agents/openai.yaml` by Codex. `run-agent.sh` copies the per-role subset into
`$CLAUDE_CONFIG_DIR/skills/` or `$CODEX_HOME/skills/` at start.

## Which agent gets what

| Skill | Career | Operations | Knowledge | Red Team | Engineering |
|---|:-:|:-:|:-:|:-:|:-:|
| `grilling` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `handoff` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `to-tickets` | | ✓ | | | ✓ |
| `to-questionnaire` | ✓ | ✓ | | | |
| `research` | | | ✓ | | |

Resident cost is the frontmatter only — bodies load on trigger. Roughly 95 tokens per
agent, ~180 for Operations. Keep it that way: anything you add here is paid on *every*
turn, by that agent, forever.

## Why these five and not the other 36

The upstream collection is written for a developer in an IDE with a repo and an issue
tracker. These agents are a **clinic**, not an operating theatre — they consult, and the
actual building happens later in Claude Code on the owner's machine. So the surgical
skills (`tdd`, `diagnosing-bugs`, `prototype`, `code-review`) are deliberately absent even
though they're good; they'd fire in a room with no patient on the table.

Two upstream facts also rule most of the rest out: 24 of the 41 skills are
`disable-model-invocation: true` (slash-command only, and Buzz has no slash UI), and many
of the remainder need a git repo or a GitHub issue tracker to do anything.

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
