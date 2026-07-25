#!/usr/bin/env bash
# Start the buzz-ai agents locally, pulling every secret from Bitwarden Secrets
# Manager at runtime. No secret is ever written to disk or baked into the image.
#
# Prereqs (install once on this machine):
#   - docker (Docker Desktop)
#   - bws   (Bitwarden Secrets Manager CLI)   https://bitwarden.com/help/secrets-manager-cli/
#   - jq
#
# Bootstrap (the ONE secret this machine needs — keep it out of Git):
#   export BWS_ACCESS_TOKEN=...      # machine-account token, read access to the project
#   export BWS_PROJECT_ID=...        # the Secrets Manager project holding the secrets
# Tip: keep these in your OS keychain / shell profile, not a committed file.
#
# Bitwarden names do NOT have to match env-var names — tools/map_secrets.py maps them
# (buzz_yc2897_agent_career_private -> CAREER_NSEC), assembles CODEX_AUTH_JSON from its
# 5 codex_* parts, and derives the allowlists from the stored *_public_hex values.
#
# NEVER put BWS_ACCESS_TOKEN in the container: agents run unsandboxed as one UID and
# would read it, then fetch every secret. bws runs here, on the host, only.
set -euo pipefail

: "${BWS_ACCESS_TOKEN:?set BWS_ACCESS_TOKEN (Bitwarden Secrets Manager machine token)}"
: "${BWS_PROJECT_ID:?set BWS_PROJECT_ID (the project holding the secrets)}"

for bin in docker bws jq python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "missing dependency: $bin" >&2; exit 1; }
done

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[start] fetching secrets from Bitwarden Secrets Manager…"
# Load every secret under its OWN Bitwarden name. Tab-delimited read handles values
# with spaces/quotes/commas (e.g. the JSON *_auth_tag values).
count=0
while IFS=$'\t' read -r key value; do
  [ -n "$key" ] || continue
  export "$key=$value"
  count=$((count + 1))
done < <(bws secret list "$BWS_PROJECT_ID" | jq -r '.[] | [.key, .value] | @tsv')
echo "[start] loaded $count secrets into the environment (not written to disk)"

# Bitwarden names them descriptively (buzz_yc2897_agent_career_private); the runtime
# wants role-shaped names (CAREER_NSEC). map_secrets.py bridges the two: it also
# assembles CODEX_AUTH_JSON from its 5 parts, derives the full-mesh allowlists from
# the stored pubkeys, and REFUSES to emit anything if a private key doesn't match its
# public key or an auth tag isn't a valid owner signature for that agent — so a
# half-finished key rotation fails here, loudly, instead of at the relay.
#
# NOTE: assign first, then eval. `eval "$(cmd)"` would report eval's own status, so a
# failed mapping would silently become a no-op and we'd start agents with nothing set.
echo "[start] mapping Bitwarden names -> runtime env vars…"
if ! mapped="$(python3 "${HERE}/tools/map_secrets.py")"; then
  echo "[start] secret mapping failed (see above) — not starting anything" >&2
  exit 1
fi
eval "$mapped"
unset mapped

# compose passes the bare-named env vars through to the container by name.
exec docker compose up -d
