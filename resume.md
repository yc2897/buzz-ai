# RESUME — where we left off

Paused mid-project (you were tired). This is the pick-up point. **Config is
complete; nothing is built or deployed yet.**

## What this project is
Run **5 personal AI agents** ("your org") always-on, off your laptop, on
**DigitalOcean App Platform** (one Worker, `supervisord` runs all 5 inside it),
talking to your **Block-hosted (Builderlab) relay**. You call them from the Buzz
desktop/mobile app.

```
You (CEO) ─ human
├── Head of Career        (Claude Code · claude-opus-4-8)
│   ├── Head of Knowledge          (Claude Code · claude-opus-4-8)
│   ├── Head of Red Team           (Codex · gpt-5.5)
│   └── Head of Engineering        (Codex · gpt-5.5)
└── Head of Operations    (Claude Code · claude-opus-4-8)
```
The hierarchy is just the mental model (it's in the prompts). For *communication*
it's a **full mesh** — all 5 can talk to each other; you can always command any.

## Fixed facts (already wired into app.yaml / run-agent.sh)
- **Relay:** `wss://yc2897.communities.buzz.xyz`
- **Owner (you):** `f6e23876ed6c7c82486c371a0f577f08c3d7025008a35900be0b7129757a1122`
- **GitHub repo (to create, private):** `yc2897/buzz-ai`
- **5 agent pubkeys (hex):** see `publickeys.txt`
- **Models:** Claude = `claude-opus-4-8`, Codex = `gpt-5.5`; **effort = `high`** (max we could verify for these runtimes; xhigh is NOT valid for Codex/Claude-Code)
- **Parallelism:** 2 workers/agent → ~10 processes → instance sized **8 GB**
- **Auth = SUBSCRIPTIONS, not API:** Claude via `CLAUDE_CODE_OAUTH_TOKEN`
  (`claude setup-token`), Codex via `CODEX_AUTH_JSON` (base64 of `~/.codex/auth.json`)

## ✅ Done (in the repo, validated by syntax/parse — NOT by a real build)
- `Dockerfile` — builds `buzz-acp` + `buzz` from pinned upstream `v0.4.22`, installs
  Node + `claude-agent-acp` + `codex-acp` + `supervisord`
- `run-agent.sh` — per-role runtime/model/effort/prompt/parallelism/auth + publishes
  each agent's kind:0 profile (name+about) on startup
- `supervisord.conf` — runs all 5
- `prompts/*.md` — the 5 system prompts (career, operations, knowledge, redteam, engineering)
- `app.yaml` — relay, owner, models, effort, full-mesh allowlists all filled;
  only SECRET values + repo are placeholders
- `agent-snapshots/*.agent.json` — desktop-import copies (source of the prompts; not used by DO)
- `.gitignore` + `codex-auth.example.json` — keep real tokens out of git

## ⏳ TODO next session (in order)
1. **Run the build (the gate):** `cd /Users/neil/buzz-ai && docker build -t buzz-ai:test .`
   — catches the real unknowns (see below) before deploying.
2. **Create private GitHub repo** `yc2897/buzz-ai`, push this directory.
3. **Generate + store the 7 secrets** (Bitwarden + DO UI):
   - `CLAUDE_CODE_OAUTH_TOKEN` ← run `claude setup-token` on your Mac (1-year, subscription)
   - `CODEX_AUTH_JSON` ← `base64 -i ~/.codex/auth.json | tr -d '\n'`
   - `CAREER_NSEC` `OPERATIONS_NSEC` `KNOWLEDGE_NSEC` `REDTEAM_NSEC` `ENGINEERING_NSEC` ← from Bitwarden
4. **Deploy:** `doctl apps create --spec app.yaml` (or paste app.yaml in the DO UI),
   then set the 7 secrets in the DO dashboard.
5. **Before/at deploy — STOP the desktop copies** of these 5 agents (the desktop
   "Stop running agents" button) so the same identity isn't running in two places.
6. **Smoke test ONE agent** (@mention it) before trusting all five.

## ⚠️ Open questions the smoke test must answer (don't assume these work)
- **Model slugs:** does `claude-opus-4-8` / `gpt-5.5` actually get accepted? Check the
  `run-agent.sh` startup log line `model=… effort=…` and that the agent replies.
  (Also: the `[1m]` 1M-context piece is NOT pinned — only the base model.)
- **Adapter CLIs:** do `claude-agent-acp` / `codex-acp` need their underlying `claude`/`codex`
  CLIs installed too? The build + first run tells us.
- **Membership / `BUZZ_AUTH_TAG`:** the closed relay may need a NIP-OA auth tag per agent
  in addition to the key. If an agent is rejected with a membership/auth error, we add
  `BUZZ_AUTH_TAG` (extract from desktop or regenerate with the owner key). Owner key is
  already set (`BUZZ_ACP_AGENT_OWNER`) for owner-recognition; this is the separate
  *membership* piece.
- **Codex subscription fragility:** `CODEX_AUTH_JSON` may break on redeploy (token
  rotation + ephemeral DO fs). If it breaks often: re-`codex login` locally → refresh the
  secret, OR move the 2 Codex agents to a Droplet w/ a persistent `~/.codex` volume, OR
  switch them to Claude (all-subscription), OR use `OPENAI_API_KEY`.

## Cost/limits watch (first day)
- Full mesh + parallelism 2 + high effort = agents chatting = **real token/subscription
  usage**. Watch your Claude/ChatGPT plan limits; they can throttle.

## Key file map
`Dockerfile` `run-agent.sh` `supervisord.conf` `app.yaml` `prompts/` `publickeys.txt`
`README.md` (full how-to) · `resume.md` (this).
