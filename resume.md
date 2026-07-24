# RESUME — where we left off

Pick-up point for buzz-ai. (Last updated 2026-07-24.)

## What this project is
Run **5 personal AI agents** ("your org") always-on, talking to your **Block-hosted
(Builderlab) relay**, callable from the Buzz desktop/mobile app.

```
You (CEO) ─ human
├── Head of Career        (Claude Code · claude-opus-4-8)
│   ├── Head of Knowledge          (Claude Code · claude-opus-4-8)
│   ├── Head of Red Team           (Codex · gpt-5.5)
│   └── Head of Engineering        (Codex · gpt-5.5)
└── Head of Operations    (Claude Code · claude-opus-4-8)
```
Hierarchy is just the mental model (in the prompts). Communication is a **full mesh**.

## ✅ Proven working (on DigitalOcean, this session)
We deployed to DO App Platform and confirmed the whole stack works end to end:
- Image builds from pinned `v0.4.22`; all 5 agents init.
- **Relay membership works** — auth tags accepted, profiles published (`{"accepted":true}`),
  no `restricted`/allowlist errors. The `BUZZ_AUTH_TAG` mechanism is validated.
- **Model slugs `claude-opus-4-8` / `gpt-5.5` accepted.**
- Codex `sqlite state runtime` collision fixed (see below).
- Agents receive DMs (react 👀) and subscribe to channels.

## 🔀 Decision: run LOCALLY, not on DO
DO at **512 MB crash-looped** — memory spikes past the cap during active turns → the
platform kills/restarts the container (that's why DMs got 👀 but no reply: killed
mid-generation). DO needs **≥2 GB** to be stable, which costs money.
**So the chosen path is local Docker Desktop on a spare computer** (Computer #1):
ample RAM (no OOM), $0 cloud cost, agents only dial out (no networking). DO still works
if you'd rather pay for ≥2 GB — `app.yaml` is intact.

## Fixed facts (wired into app.yaml / compose / run-agent.sh)
- **Relay:** `wss://yc2897.communities.buzz.xyz`
- **Owner:** `f6e23876ed6c7c82486c371a0f577f08c3d7025008a35900be0b7129757a1122`
- **GitHub:** `yc2897/buzz-ai`, branch **`v0`** (the only branch)
- **5 agent pubkeys:** in `templates/env.example` (comments) + `app.yaml` allowlists
- **Models:** `claude-opus-4-8` / `gpt-5.5`; effort `high`
- **Parallelism:** default **1** for all agents (Codex pinned to 1). Raise via `BUZZ_ACP_AGENTS` on a big local box.

## Local run (the plan) — see README "Run locally"
- **`docker-compose.yml`** — non-secret config inline; 12 secrets are bare passthroughs.
- **`start.sh`** — pulls the 12 secrets from **Bitwarden Secrets Manager** (`bws`) at
  runtime, exports them, `docker compose up -d`. Nothing on disk, nothing in the image.
- Bootstrap on Computer #1: `BWS_ACCESS_TOKEN` + `BWS_PROJECT_ID` (in shell/keychain).
- Secret keys in Bitwarden SM must equal env-var names (CAREER_NSEC, CODEX_AUTH_JSON, …).

## ⏳ TODO next session (in order)
1. **Commit the two new files** (currently untracked): `docker-compose.yml`, `start.sh`.
   ```
   git add docker-compose.yml start.sh && git commit -m "Add local docker-compose + start.sh" && git push origin v0
   ```
2. **On Computer #1:** install `docker` + `bws` + `jq`; set up Bitwarden Secrets Manager
   (project + machine token + 12 secrets); export `BWS_ACCESS_TOKEN` / `BWS_PROJECT_ID`.
3. **`./start.sh`** → first run builds the image locally → agents come up. Test with an
   `@mention`. Keep the machine awake.
4. (Optional) GitHub Action to build + push a clean image to GHCR, then switch
   `docker-compose.yml` `build: .` → `image: ghcr.io/yc2897/buzz-ai:latest`.

## ⚠️ SECURITY — rotate keys before/at load into Bitwarden SM
The 12 secrets (5 `*_NSEC`, `CLAUDE_CODE_OAUTH_TOKEN`, `CODEX_AUTH_JSON`, 5 `*_AUTH_TAG`)
were **pasted into a chat transcript this session → treat as exposed → rotate.**
- **Claude token:** re-run `claude setup-token`.
- **Codex:** `codex login` → re-encode `~/.codex/auth.json`.
- **5 agent nsecs (cascade):** new keys → new pubkeys → regenerate allowlists (`app.yaml`
  + `docker-compose.yml`) AND the 5 auth tags (`tools/gen_auth_tags.py`) → update Bitwarden SM.
- **Owner key:** if rotated, update `EXPECTED_OWNER` in `tools/gen_auth_tags.py`,
  `BUZZ_ACP_AGENT_OWNER`, and regenerate ALL auth tags (they're signed by the owner key).
- Also: delete `/workspace/secret.txt` (leaked plaintext, outside the repo).

## Key learnings (so we don't re-derive them)
- **Codex needs an isolated `CODEX_HOME` per agent** — shared `~/.codex` → sqlite state
  collision. `run-agent.sh` sets `CODEX_HOME=~/.codex-<ROLE>` + forces Codex parallelism 1.
- **buzz self-heals crashes but NOT memory.** 3-layer restart (buzz-acp respawn + circuit
  breaker 3/60s→5min cooldown → supervisord → DO container). No RSS monitoring, agent
  subprocess stays resident (idle_timeout is per-turn). So OOM is on you: size the host.
- **Context-full is handled:** Claude Code auto-compacts; base prompt says resume silently;
  durable memory lives on the relay; `BUZZ_ACP_CONTEXT_MESSAGE_LIMIT` (12) bounds history.
- **Presence (the green light)** = `kind:20001`, self-published every 30s (60s TTL). It's a
  *readout* of the process state, not a switch — you can't toggle an agent via presence.
- **On-demand agents** explored (dispatcher watches team channel → `supervisorctl start/stop`;
  or AWS Fargate scale-to-zero). Deferred — decided local-always-on is simpler for now.
  A sleeping agent can only be woken via a **channel @mention** (DMs are E2E + `#p`-gated,
  invisible to any dispatcher).

## Key file map
`Dockerfile` `run-agent.sh` `supervisord.conf` `app.yaml` (DO path) ·
`docker-compose.yml` `start.sh` (local path) · `prompts/` ·
`templates/env.example` `templates/codex-auth.example.json` · `tools/gen_auth_tags.py` ·
`README.md` (full how-to) · `resume.md` (this).
