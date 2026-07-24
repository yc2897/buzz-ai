# buzz-ai — 5 Buzz agents on DigitalOcean

Private packaging repo. Runs **5 Claude Code / Codex agents** against a
**Block-hosted (Builderlab) relay**, as **one DigitalOcean App Platform Worker**
with all 5 agents inside it (`supervisord` runs and restarts them).

Upstream Buzz source is **not** copied here — the Dockerfile clones a pinned tag
(`v0.4.22`) from `block/buzz` at build time. Updating = bump one tag. No fork, no
merge conflicts. See **`resume.md`** for the current pick-up point.

## The org

```
You (CEO) ─ human
├── Head of Career        (Claude Code · claude-opus-4-8)
│   ├── Head of Knowledge          (Claude Code · claude-opus-4-8)
│   ├── Head of Red Team           (Codex · gpt-5.5)
│   └── Head of Engineering        (Codex · gpt-5.5)
└── Head of Operations    (Claude Code · claude-opus-4-8)
```

The hierarchy is only the **mental model** (baked into the prompts). For
communication it's a **full mesh** — every agent can talk to every other, and you
(owner) can always command any of them.

## How it runs

```
DigitalOcean Worker
  └── supervisord                 ← the one program DO watches; starts + restarts all 5
       ├── career / operations / knowledge   → claude-agent-acp (Claude Code)
       └── redteam / engineering             → codex-acp        (Codex / GPT)
All 5 connect out to wss://yc2897.communities.buzz.xyz and authenticate with their keys.
```

## Files

| File | What it is |
|---|---|
| `Dockerfile` | Builds `buzz-acp` + `buzz` from pinned `v0.4.22`; installs Node, the Claude+Codex adapters, `supervisord` |
| `run-agent.sh` | Per-role launcher: runtime, model, effort, prompt, parallelism, auth, and kind:0 profile publish |
| `supervisord.conf` | Runs all 5 agents, restarts any that crash |
| `prompts/*.md` | The 5 system prompts |
| `app.yaml` | DO App Platform spec — ONE Worker |
| `codex-auth.example.json` | Template for the Codex token file (safe to commit) |
| `agent-snapshots/*.agent.json` | Desktop-import copies (source of the prompts; DO doesn't use them) |
| `publickeys.txt` | The 5 agent pubkeys (npub + hex) |

## What's already wired (in `app.yaml`)
- **Relay:** `wss://yc2897.communities.buzz.xyz`
- **Owner:** `f6e2…1122` (so you can always command any agent)
- **Models / effort:** `claude-opus-4-8` · `gpt-5.5` · effort `high`
- **Parallelism:** 2 workers/agent → instance sized **8 GB**
- **Allowlists:** full mesh (all 5)

## Auth = your subscriptions (not API keys)
- **Claude agents** → `CLAUDE_CODE_OAUTH_TOKEN`, a 1-year token from `claude setup-token`
  (subscription, headless). *(Alternative: `ANTHROPIC_API_KEY` — uncomment in `app.yaml`, set only one.)*
- **Codex agents** → `CODEX_AUTH_JSON`, base64 of your `~/.codex/auth.json` (ChatGPT subscription).
  ⚠️ Fragile — see the caveat below. *(Alternative: `OPENAI_API_KEY`.)*

## Setup

1. **Push this dir to the private repo** `yc2897/buzz-ai` (a fork of a public repo
   can't be private — this is a standalone private repo referencing upstream).
2. **Test the build first** (real Rust compile, several minutes):
   ```bash
   docker build -t buzz-ai:test .
   ```
3. **Generate the 7 secrets** and store in Bitwarden + the DO UI:
   - `CLAUDE_CODE_OAUTH_TOKEN` ← `claude setup-token`
   - `CODEX_AUTH_JSON` ← `base64 -i ~/.codex/auth.json | tr -d '\n'`
   - `CAREER_NSEC` … `ENGINEERING_NSEC` ← the 5 keys from Bitwarden
4. **Deploy:** `doctl apps create --spec app.yaml` (or paste into the DO UI), then set
   the 7 secrets in the dashboard.
5. **Stop the desktop copies** of these agents first (same keys) so one identity isn't
   running in two places.
6. **Smoke-test one agent** (@mention it) before trusting all five.

## Taking upstream updates
Bump `BUZZ_REF` (in `app.yaml` and the `Dockerfile` `ARG`) from `v0.4.22` to a newer
**tag**, then redeploy. Never point at `main`.

## Re-login loops (when auth breaks)
- **Claude:** token lasts ~1 year → re-run `claude setup-token`, update `CLAUDE_CODE_OAUTH_TOKEN`.
- **Codex:** if it stops working → `codex login` on your Mac → `base64 -i ~/.codex/auth.json | tr -d '\n'`
  → update `CODEX_AUTH_JSON` → redeploy.

## Things to remember
- **Redeploy wipes the container, not your data.** Identities (secrets) + memory (on the
  relay) survive; anything already posted/committed is not rolled back.
- **Ephemeral disk** — nothing persists between deploys. This is why the Codex `auth.json`
  method is fragile (see `resume.md` for the fix options).
- **Agents run unsandboxed inside the container**, auto-approving their own tool calls.
  Keep unrelated secrets off it.
- **Relay is Block-hosted** → channel messages/files are readable by Block; DMs + agent
  memory are end-to-end encrypted.
- **Cost/limits:** full mesh + parallelism 2 + high effort = heavy subscription usage; watch it.

## Unverified — confirm on first run (details in `resume.md`)
- The pinned tag builds cleanly with `--locked`.
- Model slugs `claude-opus-4-8` / `gpt-5.5` are accepted (the `[1m]` 1M-context is NOT pinned).
- The `claude-agent-acp` / `codex-acp` adapters don't need extra CLIs.
- Whether the closed relay needs a per-agent `BUZZ_AUTH_TAG` (membership) beyond the key.
- `instance_size_slug` names change over time — verify in the DO UI.
