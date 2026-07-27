---
name: research
description: Investigate a question against high-trust primary sources and capture the findings as a Markdown file. Use when the user wants a topic researched or docs, specs or API facts gathered and written up.
---

If you can dispatch sub-agents, fan the reading out across them and synthesise the results yourself. If you cannot, do it inline — the method below is the same either way.

1. Investigate the question against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Write the findings to a single Markdown file, citing each claim's source as a URL.
3. Save it to `research/<YYYY-MM-DD>-<slug>.md` under your working directory and report the path in chat.
4. Separate what you **verified** from what you are **inferring**. Say plainly when a source contradicts another, or when you could not find one — an unanswered question named is worth more than a confident guess.
