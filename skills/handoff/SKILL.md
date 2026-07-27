---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up. Use when the conversation has reached a conclusion the owner will act on elsewhere, or they say "write this up", "hand this off", or ask for a brief.
argument-hint: "What will the next session be used for?"
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work.

Save it to `handoffs/<YYYY-MM-DD>-<slug>.md` under your working directory, and report the path back in chat. Never save to `/tmp` or anywhere outside your working directory — only your working directory survives a restart, and the owner reads these from their own machine.

The reader is a coding agent the owner will start themselves, in a repo you cannot see. Write for that reader: state the decisions reached and the constraints agreed, not the chat history that produced them.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
