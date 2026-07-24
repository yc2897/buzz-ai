#!/usr/bin/env bash
# Start the buzz-ai agents locally, pulling the 12 secrets from Bitwarden Secrets
# Manager at runtime. No secret is ever written to disk or baked into the image.
#
# Prereqs (install once on this machine):
#   - docker (Docker Desktop)
#   - bws   (Bitwarden Secrets Manager CLI)   https://bitwarden.com/help/secrets-manager-cli/
#   - jq
#
# Bootstrap (the ONE secret this machine needs — keep it out of Git):
#   export BWS_ACCESS_TOKEN=...      # machine-account token, read access to the project
#   export BWS_PROJECT_ID=...        # the Secrets Manager project holding the 12 secrets
# Tip: keep these in your OS keychain / shell profile, not a committed file.
#
# In Bitwarden Secrets Manager, each secret's KEY must equal the env-var name:
#   CLAUDE_CODE_OAUTH_TOKEN, CODEX_AUTH_JSON,
#   CAREER_NSEC OPERATIONS_NSEC KNOWLEDGE_NSEC REDTEAM_NSEC ENGINEERING_NSEC,
#   CAREER_AUTH_TAG OPERATIONS_AUTH_TAG KNOWLEDGE_AUTH_TAG REDTEAM_AUTH_TAG ENGINEERING_AUTH_TAG
set -euo pipefail

: "${BWS_ACCESS_TOKEN:?set BWS_ACCESS_TOKEN (Bitwarden Secrets Manager machine token)}"
: "${BWS_PROJECT_ID:?set BWS_PROJECT_ID (the project holding the 12 secrets)}"

for bin in docker bws jq; do
  command -v "$bin" >/dev/null 2>&1 || { echo "missing dependency: $bin" >&2; exit 1; }
done

echo "[start] fetching secrets from Bitwarden Secrets Manager…"
# Export each secret as an env var (key=env-var name, value=secret). Tab-delimited
# read handles values with spaces/quotes/commas (e.g. the JSON *_AUTH_TAG values).
count=0
while IFS=$'\t' read -r key value; do
  [ -n "$key" ] || continue
  export "$key=$value"
  count=$((count + 1))
done < <(bws secret list "$BWS_PROJECT_ID" | jq -r '.[] | [.key, .value] | @tsv')
echo "[start] loaded $count secrets into the environment (not written to disk)"

# compose passes the bare-named env vars through to the container by name.
exec docker compose up -d
