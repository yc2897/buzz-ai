# buzz-ai — 5 Buzz agents in Docker

Private packaging repo. Runs **5 Claude Code / Codex agents** against a
**Block-hosted (Builderlab) relay**, as **one local Docker container**
with all 5 agents inside it (`supervisord` runs and restarts them).

Runs on your own machine — **no cloud deployment**. Agents only dial *out* to the relay,
so there's no inbound networking to configure, and the cost is $0. Cloud was tried and
dropped: at 512 MB the container crash-looped (memory spikes during a turn got the process
killed — DMs got 👀 but no reply), and a stable ≥2 GB instance costs real money every
month. Any machine you leave on has ample RAM. If cloud ever comes back, recover
`app.yaml` from git history rather than rewriting it.

Upstream Buzz source is **not** copied here — the Dockerfile clones a pinned tag
(`v0.4.22`) from `block/buzz` at build time. Updating = bump one tag. No fork, no
merge conflicts.

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

## Files

| File | What it is |
|---|---|
| `Dockerfile` | Builds `buzz-acp` + `buzz` from pinned `v0.4.22`; installs Node, the Claude+Codex adapters, `supervisord` |
| `run-agent.sh` | Per-role launcher: runtime, model, effort, prompt, parallelism, auth, and kind:0 profile publish |
| `supervisord.conf` | Runs all 5 agents, restarts any that crash |
| `prompts/*.md` | The 5 system prompts |
| `docker-compose.yml` | The container spec: model/relay config inline; identity + secrets injected at runtime |
| `start.py` | **The launcher** — one command on every platform: `bws` → `tools/map_secrets.py` → `docker compose up -d`. No bash, no `jq`, no `eval` |
| `templates/codex-auth.example.json` | Template for the Codex token file (safe to commit) |
| `templates/env.example` | Committed reference of every env var the container expects (public values + agent pubkeys as comments) |
| `agent-snapshots/*.agent.json` | Desktop-import copies (source of the prompts; the container doesn't use them) |
| `tools/gen_auth_tags.py` | Mints the 5 `*_AUTH_TAG` NIP-OA owner attestations (needs your owner key + the pubkeys) |
| `tools/map_secrets.py` | Host-side adapter: maps the Bitwarden secret names onto the env vars the runtime wants, assembles `CODEX_AUTH_JSON`, derives the allowlists, and verifies keypairs + auth tags before anything starts |

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

## Running it

Run the one container on a machine you keep awake. Plenty of RAM (no cloud memory cap
→ no OOM), and agents only dial *out* to the relay.

Secrets are injected **at runtime** from Bitwarden Secrets Manager — never written to
disk or baked into the image.

**Once:** install `docker` and `bws` (Bitwarden Secrets Manager CLI). In Bitwarden
Secrets Manager create a project + a machine account (read on that project), and add
your secrets — the names don't have to match the env vars, `tools/map_secrets.py`
handles that. Then set the bootstrap values in your shell/keychain:
```bash
export BWS_ACCESS_TOKEN=...   # machine-account token
export BWS_PROJECT_ID=...     # the project holding the secrets
```

**Every time (one command):**
```bash
python3 start.py            # start  (same command on macOS, Linux and Windows)
python3 start.py --check    # validate secrets, start nothing
python3 start.py --down     # stop
```

### Cross-platform notes

The launcher is `start.py` — Python rather than shell, for three reasons that all bit us
in practice:

- **CRLF immunity.** A `.sh` checked out with Windows line endings cannot run *at all* —
  the kernel looks for an interpreter named `bash\r` and fails before the first line, so
  no guard inside the script could ever help. Python's parser accepts either ending.
  `.gitattributes` pins LF as the real fix; `start.py` is the belt to that braces.
- **No `jq`.** `bws`'s JSON is parsed natively, so that's one less dependency to install.
- **No `eval`.** Secrets go straight from `bws` into the `docker compose` subprocess
  environment. They never touch a shell command line, your shell history, or the
  environment of anything else you run in that terminal afterwards.

**On Windows, use WSL2** (Docker Desktop uses it as the backend anyway). Clone into the
WSL filesystem — `~/buzz-ai`, not `/mnt/c/...` — which avoids CRLF entirely and is far
faster for the Rust build. If you already have a CRLF checkout, repair it once with
`sed -i 's/\r$//' *.py tools/*.py`.

The image is **architecture-specific**: npm resolves the Claude SDK binary at build time
(`…-linux-arm64` on Apple Silicon, `…-linux-x64` on a PC). Don't copy an image between
machines — let `build: .` rebuild and it resolves correctly on its own.

⚠️ **Never run two machines at once.** Both hold the same five nsecs, so you'd get every
message answered twice plus racing writes to the same memory slugs. `--down` one first.
First run builds the image locally (several minutes — a real Rust compile). A build
behind a TLS-inspecting corporate proxy will fail at the crates.io step; build at home.
If you later publish to GHCR, swap `build: .` → `image: ghcr.io/yc2897/buzz-ai:latest`
in `docker-compose.yml` to pull instead of build.

⚠️ **Never pass `BWS_ACCESS_TOKEN` into the container.** `bws` runs on your Mac; the
container receives only the finished values. A token inside the container is readable
by every agent, and it keeps working after the container is gone.

## If an agent seems unresponsive

Read the channel straight off the relay, bypassing the desktop app — if the reply is here
but not in the app, the problem is the app (stale member cache), not the agent:

```bash
docker exec buzz-ai-agents-1 sh -c \
  'BUZZ_PRIVATE_KEY="$OPERATIONS_NSEC" BUZZ_AUTH_TAG="$OPERATIONS_AUTH_TAG" \
   buzz messages get --channel <channel-id> --limit 10'
```

Other quick checks: `docker compose logs -f`, and confirm the agent isn't simply idle
because it was never added to the channel.

## Taking upstream updates
Bump `BUZZ_REF` (the `Dockerfile` `ARG`) from `v0.4.22` to a newer **tag**, then
`docker compose build && python3 start.py`. Never point at `main`.

## Re-login loops (when auth breaks)
- **Claude:** token lasts ~1 year → re-run `claude setup-token`, update the
  `claude_oauth_token` secret in Bitwarden.
- **Codex:** if it stops working → `codex login` on your Mac → update the five
  `codex_*` secrets in Bitwarden from the new `~/.codex/auth.json`.

Either way: `python3 start.py --down && python3 start.py` to pick up the new values.

## Rotating credentials (runbook)

> ✅ A full rotation (owner key + all 5 agent keys) was completed 2026-07-25. This is the
> reusable procedure for next time. Do the steps in order: step 3 needs the pubkeys from
> step 2, and **step 0 is irreversible if skipped**.

**Independent vs. cascading** — only the agent keys are expensive:

| Secret | Blast radius |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | self-contained — mint a new token, done |
| `CODEX_AUTH_JSON` | self-contained — re-encode `auth.json`, done |
| 5 × `*_NSEC` | **cascades** → 5 new pubkeys → `templates/env.example` + `gen_auth_tags.py` + Bitwarden `*_public_hex` → 5 new `*_AUTH_TAG` |
| owner key | **widest** — every auth tag is *signed by it*, so all 5 must be re-minted, plus `EXPECTED_OWNER` + `BUZZ_ACP_AGENT_OWNER` |

Rotating the owner key is the expensive one — every auth tag is signed by it, so all 5
must be re-minted. Either way the relay needs **no action from Block**: an auth tag is an
*owner attestation*, so freshly signed tags are accepted exactly as the current ones were.

Since `docker-compose.yml` now derives `BUZZ_ACP_AGENT_OWNER` and the allowlists from
Bitwarden, updating the `*_public_hex` secrets is what actually takes effect at runtime;
the committed files are reference.

### Step 0 — Save agent memory FIRST (else it's gone)

Agent memory (NIP-AE engrams, kind `30174`) is authored by the **agent's pubkey** and
NIP-44-encrypted under `conversation_key(agent_secret, owner_pubkey)` — and the lookup
`d` tag is derived from that same key. A new nsec is therefore **a new agent with
amnesia**: the old engrams stay on the relay, unreadable *and* unaddressable. There is no
migration path after the fact. Export anything worth keeping now.

`buzz` isn't installed on the Mac — it lives in the image, so run it through Docker:

```bash
OWNER=a4753e3ba9c4c812a052dfe4e414e14469d3c60d09dbd07f76d3d70236445826
RELAY=wss://yc2897.communities.buzz.xyz

# list slugs for one agent (repeat per agent, with that agent's CURRENT nsec)
docker run --rm -e BUZZ_RELAY_URL="$RELAY" -e BUZZ_PRIVATE_KEY="<OLD_CAREER_NSEC>" \
  buzz-ai:local buzz mem ls --owner "$OWNER" --json

# save one slug's value
docker run --rm -e BUZZ_RELAY_URL="$RELAY" -e BUZZ_PRIVATE_KEY="<OLD_CAREER_NSEC>" \
  buzz-ai:local buzz mem get <slug> --owner "$OWNER" > career-<slug>.txt
```

After the new keys are live, re-seed with `buzz mem set <slug> -` (value on stdin).
If `buzz-ai:local` doesn't exist yet, `docker compose build` first.

### Step 1 — Brain auth (independent; safe to do anytime)

```bash
claude setup-token                        # → CLAUDE_CODE_OAUTH_TOKEN (~1 year)
codex login && base64 -i ~/.codex/auth.json | tr -d '\n'   # → CODEX_AUTH_JSON
```

### Step 2 — The 5 agent identities

Generate five fresh keypairs. `buzz-admin` isn't in the image (the Dockerfile builds only
`buzz-acp` + `buzz-cli`), so build it from your pinned upstream checkout — the first build
is slow, it pulls the relay's dependency tree:

```bash
cd /Users/neil/workspace_buzz/buzz && git checkout v0.4.22
cargo run -q -p buzz-admin -- generate-key      # run 5× — needs no database
```

Keep the `Public key:` (64-hex) and `Secret key:` for each. Copy the secret **verbatim**;
`*_NSEC` accepts either hex or `nsec1…` (buzz calls `Keys::parse` —
`crates/buzz-acp/src/config.rs:735`), as does `tools/gen_auth_tags.py`.

Then update the pubkeys in these tracked files (and the `*_public_hex` secrets in Bitwarden):

| Where | What to replace |
|---|---|
| **Bitwarden** | the 5 `*_public_hex` (and `*_public_npub`) secrets — **this is what actually takes effect** |
| `templates/env.example` | the 5 `*_ALLOWLIST` values **and** the npub/hex comment block (reference only) |
| `tools/gen_auth_tags.py` | the 5 pubkeys in the `AGENTS` list |

`docker-compose.yml` needs **no** edit — it takes `BUZZ_ACP_AGENT_OWNER` and all 5
allowlists from Bitwarden via `tools/map_secrets.py`, which is exactly what stops a
rotation from leaving a stale pubkey behind.

Each agent's allowlist is **the other four** pubkeys — never its own. You (owner) are
always implicitly allowed and never belong in a list (`run-agent.sh:107`). To build the
five lines without hand-assembly errors (**run under `bash`**, not zsh — `${!var}` is
bash indirect expansion):

```bash
CAREER=<hex>; OPERATIONS=<hex>; KNOWLEDGE=<hex>; REDTEAM=<hex>; ENGINEERING=<hex>
for r in CAREER OPERATIONS KNOWLEDGE REDTEAM ENGINEERING; do
  out=""
  for o in CAREER OPERATIONS KNOWLEDGE REDTEAM ENGINEERING; do
    [ "$r" = "$o" ] || out="${out:+$out,}${!o}"
  done
  echo "${r}_ALLOWLIST=$out"
done
```

Sanity check before moving on: each line has exactly 4 comma-separated 64-hex values, and
no line contains its own role's pubkey.

### Step 3 — Re-mint the 5 auth tags

Only after `AGENTS` in `tools/gen_auth_tags.py` holds the new pubkeys:

```bash
cd /Users/neil/workspace_buzz/buzz-ai
python3 tools/gen_auth_tags.py     # hidden prompt for the owner key
```

It verifies the owner key against `EXPECTED_OWNER` and refuses to generate on mismatch,
self-verifies all 5 BIP-340 signatures, and writes `tools/auth_tags.local` (mode `600`,
git-ignored). **Delete that file once the values are in Bitwarden.** If you rotated the
owner key too, update `EXPECTED_OWNER` first and the `buzz_yc2897_public_hex` secret in
Bitwarden (plus `templates/env.example` for reference).

### Step 4 — Load Bitwarden, commit, verify

1. Put the new values in Bitwarden SM. Names are **free-form** — `tools/map_secrets.py`
   maps them (`buzz_yc2897_agent_career_private` → `CAREER_NSEC`). Store each auth tag as
   the bare `["auth",…]` array: no `NAME=` prefix, one tag per secret.
2. Verify before starting anything: `python3 tools/map_secrets.py --check` should report
   18 vars ready. It re-derives every pubkey from its private key and checks every auth
   tag's signature, so a half-finished rotation fails here rather than at the relay.
3. Commit the pubkey changes — they're public:
   ```bash
   git add templates/env.example tools/gen_auth_tags.py
   git commit -m "Rotate agent keys: new pubkeys, allowlists, auth tags" && git push origin v0
   ```
4. `rm tools/auth_tags.local`, then `python3 start.py`.
5. **Add the new agents to a channel.** Fresh pubkeys are members of nothing, so they log
   `discovered 0 channel(s) — agent will sit idle`. They're subscribed to membership
   notifications, so adding them takes effect live (`lib.rs:1892`) — no restart. Then
   @mention one.
6. The 5 agents appear in the Buzz app as **new contacts**; the old identities are dead.
   Stop/remove those desktop entries — if the app still runs agents on the same keys,
   every message gets answered twice. `kind:0` profiles republish at startup
   (`run-agent.sh:118`), so the names come back on their own.

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

## Verified working (2026-07-25, local)
- All 5 agents build, start under supervisord, connect, and publish profiles.
- Model slugs `claude-opus-4-8` / `gpt-5.5` accepted (the `[1m]` 1M-context is NOT pinned).
- The `claude-agent-acp` / `codex-acp` adapters need no extra CLIs.
- `BUZZ_AUTH_TAG` works and is load-bearing: each agent logs
  `owner resolved from BUZZ_AUTH_TAG: a4753e3b…`, and every message it posts carries that
  tag and is accepted by the relay.
- Channel @mentions answered in ~6–20s (opus, effort `high`).
- Idle footprint ~312 MB of 7.65 GB — the same workload that OOM-looped at 512 MB.

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

## Next steps

1. **Consider splitting into 5 containers**, one per agent. Today every secret sits in
   every agent's environment: `buzz-acp` spawns the agent with no `env_clear()`
   (`crates/buzz-acp/src/acp.rs:416`) and supervisord passes its whole environment through,
   so any one agent can read the other four's keys and both subscription tokens. Splitting
   gives real per-agent isolation with one token and one Bitwarden project.
2. *(Optional)* GitHub Action to build and push the image to GHCR, then switch
   `docker-compose.yml` `build: .` → `image: ghcr.io/yc2897/buzz-ai:latest`.
