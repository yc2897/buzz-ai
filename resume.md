# RESUME — where we left off

Pick-up point for the buzz-ai deploy. **Config + auth tags are done; nothing is
pushed or deployed yet.** (Last updated 2026-07-24.)

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
Hierarchy is just the mental model (it's in the prompts). Communication is a
**full mesh** — all 5 can talk; you can always command any.

## Fixed facts (wired into app.yaml / run-agent.sh)
- **Relay:** `wss://yc2897.communities.buzz.xyz`
- **Owner (you):** `f6e23876ed6c7c82486c371a0f577f08c3d7025008a35900be0b7129757a1122`
- **GitHub repo:** `yc2897/buzz-ai`, branch **`v0`** (the only branch; app.yaml points here)
- **5 agent pubkeys (hex):** see `publickeys.txt`
- **Models:** Claude `claude-opus-4-8`, Codex `gpt-5.5`; **effort `high`** (xhigh invalid here)
- **Parallelism:** 2 workers/agent → ~10 processes → instance **8 GB**
- **Auth = SUBSCRIPTIONS, not API:** Claude `CLAUDE_CODE_OAUTH_TOKEN`, Codex `CODEX_AUTH_JSON`

## How the deploy actually works (important)
`app.yaml` uses the **build-from-source** model (`github:` + `dockerfile_path:`),
so **DO pulls the pushed GitHub source, builds the image itself, then runs it.**
It does NOT pull a pre-built image. Consequences:
- Only what you **push to `v0`** gets built. Uncommitted local edits do nothing.
- DO's builder is **not** behind SharkNinja's proxy, so the crates.io TLS error a
  local `docker build` hits on the corp network does NOT affect DO. **DO's build
  log is the real gate.** A local build is optional convenience only.

## ✅ Done this session
- **`tools/gen_auth_tags.py`** — pure-Python BIP-340 generator for the NIP-OA
  `BUZZ_AUTH_TAG` owner attestations. Validated against all 27 canonical BIP-340
  test vectors + the NIP-19 nsec vector. Reads the owner key via file/stdin (never
  argv), verifies it derives the owner pubkey, self-verifies each signature, writes
  `auth_tags.local` (chmod 600), shreds the key file.
- **All 5 auth tags minted** and (per you) recorded into DO + Bitwarden.
- **`run-agent.sh`** — maps `<ROLE>_AUTH_TAG` → `BUZZ_AUTH_TAG`, exported before the
  profile publish; startup log shows `auth_tag=set(...)`/`UNSET…`.
- **`app.yaml`** — added the 5 `*_AUTH_TAG` SECRET slots; fixed `branch: main` → `v0`.
- **`Dockerfile`** — strips CRLF from `run-agent.sh` + `supervisord.conf` so a Windows
  checkout doesn't ship broken scripts.
- **Docs** — README secret count 7→12, added the auth-tag generation step + tools row.

## ⏳ TODO next (in order)
1. **Commit + push** the above to `yc2897/buzz-ai` branch `v0`.
2. **Record remaining secrets** in DO + Bitwarden (auth tags already recorded):
   - `CLAUDE_CODE_OAUTH_TOKEN` ← `claude setup-token`
   - `CODEX_AUTH_JSON` ← `base64 -i ~/.codex/auth.json | tr -d '\n'`
   - `CAREER_NSEC` … `ENGINEERING_NSEC` ← from Bitwarden
   → **12 secrets total.**
3. **Deploy:** connect the repo in DO / `doctl apps create --spec app.yaml`, set the 12 secrets.
4. **STOP the desktop copies** of these 5 agents (same keys — don't run one identity twice).
5. **Smoke-test ONE agent** (@mention it) before trusting all five. Watch the DO
   build log (compile gate) and the `[run-agent] … model=… auth_tag=…` startup line.

## ⚠️ Open questions the smoke test must answer
- **Model slugs:** does `claude-opus-4-8` / `gpt-5.5` get accepted? (`[1m]` NOT pinned.)
- **Adapter CLIs:** do `claude-agent-acp` / `codex-acp` need the underlying `claude`/`codex` CLIs?
- **Relay membership:** the auth tags are now generated + wired, so if the relay requires
  NIP-OA membership it's covered. Watch for `restricted: not a relay member` (tag issue)
  vs `pubkey not in allowlist` (needs the operator to add the pubkeys — a tag won't fix that).
- **Codex fragility:** `CODEX_AUTH_JSON` may break on redeploy (token rotation + ephemeral
  fs). Fixes: re-`codex login` → refresh secret; or persistent Droplet volume; or switch
  the 2 Codex agents to Claude; or `OPENAI_API_KEY`.

## Cost/limits watch (first day)
Full mesh + parallelism 2 + high effort = real token/subscription usage. Watch your
Claude/ChatGPT plan limits; they can throttle.

## Key file map
`Dockerfile` `run-agent.sh` `supervisord.conf` `app.yaml` `prompts/` `publickeys.txt`
`tools/gen_auth_tags.py` · `README.md` (full how-to) · `resume.md` (this).
