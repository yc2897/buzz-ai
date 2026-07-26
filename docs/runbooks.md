# Rare procedures

Long, step-by-step operations you do once in a while. Follow them in order.

> Part of **buzz-ai** — see [README](../README.md) for the map.

## Rotating credentials

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

## Restoring from a backup

**Restore** — `BACKUP_LATEST_SYMLINK` means you don't need to look up a timestamp:
```bash
docker compose down
docker run --rm -v buzz-ai_agent-home:/data -v "$PWD/backups":/in \
  debian:stable-slim tar xzf /in/buzz-ai-latest.tar.gz -C /data
python3 start.py
```

Use a dated filename instead of `-latest` to roll back to a specific night. The
`--strip-components=2` matters: the archive stores paths as `/backup/agent-home/...`.
