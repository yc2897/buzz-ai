# How it works, and why

Design, layout, and the decisions behind them. Read this when you're picking the project
back up after a gap, or wondering *why* something is the way it is.

> Part of **buzz-ai** — see [README](../README.md) for the map.

## The org

```
You (CEO) ─ human
├── Career        (Claude Code · claude-opus-4-8)
├── Operations    (Claude Code · claude-opus-4-8)
├── Knowledge     (Claude Code · claude-opus-4-8)
├── Red Team      (Codex · gpt-5.5)
└── Engineering   (Codex · gpt-5.5)
```

**Flat by design.** All five report directly to you and none outranks another —
the prompts say so explicitly. Communication is a **full mesh**: every agent can
@mention every other to pull them into a problem, and you can command any of them.
Structure and communication now match, so there's no hierarchy to keep in your head.

## How it runs

```
Your Mac
  └── docker container
       └── supervisord            ← the container's one process; starts + restarts all 5
            ├── career / operations / knowledge   → claude-agent-acp (Claude Code)
            └── redteam / engineering             → codex-acp        (Codex / GPT)
All 5 connect out to wss://yc2897.communities.buzz.xyz and authenticate with their keys.
```

The Buzz desktop app is **not** required for the agents to run — it's just how you talk
to them. They stay up whether or not it's open; `buzz` on the CLI works too.

## What's already wired
- **Relay:** `wss://yc2897.communities.buzz.xyz`
- **Owner:** `a475…5826` (so you can always command any agent)
- **Repo:** `yc2897/buzz-ai`, branch **`v0`** (the only branch)
- **Bitwarden project:** `cc98e161-4b47-4ce0-b1cb-b492003be740` (26 secrets)
- **Test channel:** `f0c72e5c-7e2e-4af8-ad09-11a1e735a869` (all 5 are members)
- **Models / effort:** `claude-opus-4-8` · `gpt-5.5` · effort `high`
- **Parallelism:** 1 worker/agent (default in `run-agent.sh`; set `BUZZ_ACP_AGENTS` to raise it — Codex stays pinned to 1)
- **Allowlists:** full mesh (all 5)

## Auth = your subscriptions (not API keys)
- **Claude agents** → `CLAUDE_CODE_OAUTH_TOKEN`, a 1-year token from `claude setup-token`
  (subscription, headless). *(Alternative: `ANTHROPIC_API_KEY` — set only one.)*
- **Codex agents** → `CODEX_AUTH_JSON`, base64 of your `~/.codex/auth.json` (ChatGPT subscription).
  ⚠️ Fragile: Codex rotates these tokens locally, so a captured copy goes stale over time —
  re-capture when the Codex agents start failing auth (see *Re-login loops*).
  *(Alternative: `OPENAI_API_KEY`.)*

## Folder structure

### This repo (on your Mac)

```text
buzz-ai/
├── start.py                    THE launcher, every platform: bws → map_secrets →
│                               docker compose up. No bash, no jq, no eval
├── docker-compose.yml          services, the agent-home volume, backup sidecar;
│                               model/relay config inline, secrets injected at runtime
├── Dockerfile                  builds buzz-acp + buzz from pinned v0.4.22; installs
│                               Node, the Claude + Codex adapters, supervisord
├── run-agent.sh                per-role launcher: runtime, model, effort, prompt,
│                               cwd, parallelism, auth, kind:0 profile publish
├── supervisord.conf            runs all 5 agents, restarts any that crash
├── prompts/                    the 5 system prompts — COPYd into the image
│   └── career.md · operations.md · knowledge.md · redteam.md · engineering.md
├── tools/
│   ├── map_secrets.py          Bitwarden names → runtime env vars; assembles
│   │                           CODEX_AUTH_JSON, derives allowlists, and verifies
│   │                           every keypair + auth tag before anything starts
│   └── gen_auth_tags.py        mints the 5 NIP-OA auth tags (needs your owner key)
├── templates/
│   ├── env.example             reference: every env var the container expects
│   └── codex-auth.example.json shape of ~/.codex/auth.json
├── agent-snapshots/            desktop-import copies; systemPrompt/about are synced
│                               from prompts/ and run-agent.sh (container ignores them)
├── backups/                    ← git-ignored; the sidecar writes archives here
├── .gitattributes              pins LF so a Windows checkout can't break the scripts
├── .gitignore                  keeps secrets, auth_tags.local and backups/ out of git
└── README.md
```

### Inside the container

Only `/home/agent` is on the volume. Everything else comes from the image and **resets on
every restart** — verified by writing to both and restarting.

```text
/                                        ← from the IMAGE, resets each restart
├── usr/local/bin/{buzz,buzz-acp}          the two Rust binaries
├── usr/local/lib/node_modules/            claude-agent-acp + codex-acp
│   └── …/claude-agent-sdk-linux-arm64/    the real 260 MB claude binary
├── opt/buzz-prompts/*.md                  copied from prompts/ at build time
├── etc/supervisor/agents.conf             copied from supervisord.conf
└── tmp/                                   EPHEMERAL — anything written here is lost

/home/agent                              ← VOLUME agent-home — PERSISTS
├── work/                                  role names are UPPERCASE (run-agent.sh $ROLE)
│   ├── CAREER/                            cwd for Career — its git clones live here
│   ├── OPERATIONS/  KNOWLEDGE/  REDTEAM/  ENGINEERING/
├── .claude-CAREER/                        per-role: config, plugins, auto-memory
├── .claude-OPERATIONS/   .claude-KNOWLEDGE/
├── .codex-REDTEAM/                        Codex SQLite state + auth.json
├── .codex-ENGINEERING/                    (auth.json is excluded from backups)
└── .local/                                pip install --user lands here
```

**Practical consequence:** agents work in `~/work/<ROLE>`, so their clones and files persist.
Anything an agent writes outside `/home/agent` — `/tmp`, a global npm install — is gone on
restart. The agents can't write to `/usr/local` anyway (root-owned, they're uid 1001).

## The agents' disk

The agents have a persistent disk: the named volume `agent-home`, mounted at
`/home/agent`. Git clones, downloaded files, `pip install --user` packages and work in
progress all survive restarts.

Each agent gets its own working directory, `~/work/<ROLE>`, because `buzz-acp` takes the
agent's cwd from `current_dir()` — without that, all five would `git clone` into the same
folder. Each Claude agent also gets its own `CLAUDE_CONFIG_DIR` (`~/.claude-<ROLE>`), which
separates their plugins and their Claude Code auto-memory; sharing one `~/.claude` meant
Career, Operations and Knowledge all wrote to the same memory directory.

It's a **named volume, not a bind mount** — Docker manages it inside the Docker VM, so it
exposes nothing from your Mac and the isolation described under *Things to remember* holds.

**What still won't persist:** system-wide installs. `/usr/local` is root-owned and the
agents run as uid 1001, so `npm install -g` and `apt-get install` both fail. That's the
non-root sandboxing working as intended — if an agent genuinely needs a system package,
add it to the `Dockerfile`.

## Things to remember
- **Restarting wipes the container, not your data.** Identities (in Bitwarden) + memory
  (on the relay) survive; anything already posted/committed is not rolled back.
- **Ephemeral disk** — nothing persists between runs. That's by design: no secret ever
  lands on the container's filesystem.
- **Agents run unsandboxed inside the container**, auto-approving their own tool calls,
  all five as the same UID. Any one of them can read every secret in the container's
  environment — the other four agents' keys and both subscription tokens included.
  Keep unrelated secrets off it, and never put `BWS_ACCESS_TOKEN` inside.
- **No host filesystem is mounted** (`docker-compose.yml` declares no `volumes:`), so the
  agents cannot reach `~/.ssh`, `~/.codex`, or anything else on your Mac. If you ever add
  a bind mount, that boundary is gone — mount one narrow path read-only, never the
  Docker socket.
- **Relay is Block-hosted** → channel messages/files are readable by Block; DMs + agent
  memory are end-to-end encrypted.
- **Cost/limits:** full mesh + high effort = heavy subscription usage; watch it.

## Key learnings (so we don't re-derive them)

- **Codex needs an isolated `CODEX_HOME` per agent.** A shared `~/.codex` collides on
  SQLite state (`failed to initialize sqlite state runtime`). `run-agent.sh` sets
  `CODEX_HOME=~/.codex-<ROLE>` and pins Codex parallelism to 1 — a second worker in one
  agent would share that home and collide the same way.
- **buzz self-heals crashes but NOT memory.** Three restart layers (buzz-acp respawns the
  agent, a circuit breaker trips at 3 failures/60s into a 5-min cooldown, then supervisord,
  then Docker). Nothing monitors RSS, and the agent subprocess stays resident between turns
  (`idle_timeout` is per-turn). So OOM is on you: size the host, don't expect a rescue.
- **Context-full is handled.** Claude Code auto-compacts, the base prompt tells the agent to
  resume silently, durable memory lives on the relay, and `BUZZ_ACP_CONTEXT_MESSAGE_LIMIT`
  (12) bounds replayed history.
- **Presence (the green dot) is `kind:20001`**, self-published every 30s with a 60s TTL.
  It's a *readout* of process state, not a switch — you can't toggle an agent via presence.
- **On-demand agents were explored and deferred** (a dispatcher watching a team channel
  driving `supervisorctl start/stop`, or scale-to-zero on Fargate). Local always-on is
  simpler, and a sleeping agent can only be woken by a **channel @mention** — DMs are
  end-to-end encrypted and `#p`-gated, so no dispatcher can see them.

## Verified working (2026-07-26, local)
- All 5 agents build, start under supervisord, connect, and publish profiles.
- Model slugs `claude-opus-4-8` / `gpt-5.5` accepted (the `[1m]` 1M-context is NOT pinned).
- The `claude-agent-acp` / `codex-acp` adapters need no extra CLIs.
- `BUZZ_AUTH_TAG` works and is load-bearing: each agent logs
  `owner resolved from BUZZ_AUTH_TAG: a4753e3b…`, and every message it posts carries that
  tag and is accepted by the relay.
- Channel @mentions answered in ~6–20s (opus, effort `high`).
- Idle footprint ~312 MB of 7.65 GB — the same workload that OOM-looped at 512 MB.

## Next steps

1. **Consider splitting into 5 containers**, one per agent. Today every secret sits in
   every agent's environment: `buzz-acp` spawns the agent with no `env_clear()`
   (`crates/buzz-acp/src/acp.rs:416`) and supervisord passes its whole environment through,
   so any one agent can read the other four's keys and both subscription tokens. Splitting
   gives real per-agent isolation with one token and one Bitwarden project.
2. *(Optional)* GitHub Action to build and push the image to GHCR, then switch
   `docker-compose.yml` `build: .` → `image: ghcr.io/yc2897/buzz-ai:latest`.
