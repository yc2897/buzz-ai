#!/usr/bin/env bash
# Launch ONE Buzz agent for the given role.
#
#   Usage: run-agent.sh <ROLE>     e.g.  run-agent.sh CAREER
#
# supervisord calls this once per agent. It maps the role to a runtime + a
# system-prompt file + a model + a profile, publishes the agent's kind:0
# profile (so it shows up named), then hands off to buzz-acp.
#
# Roles -> runtime:
#   CAREER, OPERATIONS, KNOWLEDGE  -> claude-agent-acp (Claude Code)
#   REDTEAM, ENGINEERING           -> codex-acp        (Codex / GPT)
#
# Per-role env vars (set in DO):
#   <ROLE>_NSEC       (SECRET) the agent's Nostr private key    — REQUIRED
#   <ROLE>_ALLOWLIST  comma-separated 64-hex pubkeys it obeys   — optional
#   <ROLE>_AUTH_TAG   (SECRET) NIP-OA owner attestation, ["auth",...] JSON;
#                     grants relay membership on a closed relay      — optional
# Shared env vars:
#   BUZZ_RELAY_URL     wss://... your Block-hosted relay         — REQUIRED
#   ANTHROPIC_API_KEY  (SECRET) brain for the Claude agents      — required for claude roles
#   OPENAI_API_KEY     (SECRET) brain for the Codex agents       — required for codex roles
#   CLAUDE_MODEL / CODEX_MODEL / CLAUDE_EFFORT / CODEX_EFFORT / BUZZ_ACP_AGENTS  (defaults below)
set -euo pipefail

ROLE="${1:?usage: run-agent.sh <ROLE>}"
PROMPT_DIR="/opt/buzz-prompts"

# Model + effort defaults — override in DO without editing this file.
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-opus-4-8}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.5}"
CLAUDE_EFFORT="${CLAUDE_EFFORT:-high}"
CODEX_EFFORT="${CODEX_EFFORT:-high}"

case "${ROLE}" in
  CAREER)      RUNTIME="claude-agent-acp"; PROMPT="${PROMPT_DIR}/career.md";      NAME="Head of Career";      ABOUT="Mentor · resume · interview · career strategy. Leads the Career team; reports to the CEO." ;;
  OPERATIONS)  RUNTIME="claude-agent-acp"; PROMPT="${PROMPT_DIR}/operations.md";  NAME="Head of Operations";  ABOUT="Planning, coordination, tracking, logistics. Reports to the CEO." ;;
  KNOWLEDGE)   RUNTIME="claude-agent-acp"; PROMPT="${PROMPT_DIR}/knowledge.md";   NAME="Head of Knowledge";   ABOUT="Learning & research. On the Career team; reports to Head of Career." ;;
  REDTEAM)     RUNTIME="codex-acp";        PROMPT="${PROMPT_DIR}/redteam.md";     NAME="Head of Red Team";    ABOUT="Constructive devil's advocate — stress-tests plans and decisions. On the Career team; reports to Head of Career." ;;
  ENGINEERING) RUNTIME="codex-acp";        PROMPT="${PROMPT_DIR}/engineering.md"; NAME="Head of Engineering"; ABOUT="Code, systems, debugging, technical evaluation. On the Career team; reports to Head of Career." ;;
  *) echo "run-agent: unknown role '${ROLE}'" >&2; exit 1 ;;
esac

[ -f "${PROMPT}" ] || { echo "run-agent: missing prompt file ${PROMPT}" >&2; exit 1; }

nsec_var="${ROLE}_NSEC"
allow_var="${ROLE}_ALLOWLIST"
authtag_var="${ROLE}_AUTH_TAG"

export BUZZ_PRIVATE_KEY="${!nsec_var:?missing env ${nsec_var}}"
export BUZZ_RELAY_URL="${BUZZ_RELAY_URL:?missing env BUZZ_RELAY_URL}"

# NIP-OA owner attestation (relay membership on a closed relay). Optional: empty
# is treated as unset by buzz-acp/buzz-cli. Exported before the profile publish
# below so that first relay connection also carries membership.
export BUZZ_AUTH_TAG="${!authtag_var:-}"
if [ -n "${BUZZ_AUTH_TAG}" ]; then
  AUTHTAG_SHOWN="set(${authtag_var})"
else
  AUTHTAG_SHOWN="UNSET — relies on owner-recognition only; closed relay may reject"
fi
export BUZZ_ACP_AGENT_COMMAND="${RUNTIME}"
export BUZZ_ACP_SYSTEM_PROMPT_FILE="${PROMPT}"
# Parallelism: 1 worker subprocess per agent (simplest; one turn at a time, lightest
# on RAM). Override per deploy via the BUZZ_ACP_AGENTS env var. Codex is always
# pinned to 1 below regardless (shared-SQLite-state constraint).
export BUZZ_ACP_AGENTS="${BUZZ_ACP_AGENTS:-1}"

# Model + brain key, per runtime.
if [ "${RUNTIME}" = "claude-agent-acp" ]; then
  # Auth: prefer your SUBSCRIPTION via CLAUDE_CODE_OAUTH_TOKEN (from `claude
  # setup-token`, 1-year, headless). ANTHROPIC_API_KEY (pay-per-token) also
  # works. Need at least one; don't set both (the API key would win).
  if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "run-agent: Claude agents need CLAUDE_CODE_OAUTH_TOKEN (subscription) or ANTHROPIC_API_KEY (API)" >&2
    exit 1
  fi
  export ANTHROPIC_MODEL="${CLAUDE_MODEL}"
  export CLAUDE_CODE_EFFORT_LEVEL="${CLAUDE_EFFORT}"
  MODEL_SHOWN="${CLAUDE_MODEL} effort=${CLAUDE_EFFORT}"
else
  # Per-role Codex home. Codex keeps a per-home SQLite state under $CODEX_HOME
  # (default ~/.codex). Two Codex agents sharing one home — or two parallel
  # workers of one agent — collide on that state ("failed to initialize sqlite
  # state runtime under /home/agent/.codex"). Give each role its own home.
  export CODEX_HOME="${HOME}/.codex-${ROLE}"
  mkdir -p "${CODEX_HOME}"
  # One worker per Codex agent: within-agent parallelism would spawn a second
  # codex process sharing this same CODEX_HOME and collide on the SQLite state.
  export BUZZ_ACP_AGENTS=1

  # Auth: prefer ChatGPT SUBSCRIPTION via a transplanted auth.json (base64 in
  # CODEX_AUTH_JSON); else OPENAI_API_KEY (API billing). Need at least one.
  if [ -n "${CODEX_AUTH_JSON:-}" ]; then
    printf '%s' "${CODEX_AUTH_JSON}" | base64 -d > "${CODEX_HOME}/auth.json"
    chmod 600 "${CODEX_HOME}/auth.json"
    echo "[run-agent] wrote ${CODEX_HOME}/auth.json from CODEX_AUTH_JSON (subscription auth)"
  elif [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "run-agent: Codex agents need CODEX_AUTH_JSON (subscription) or OPENAI_API_KEY (API)" >&2
    exit 1
  fi
  # Codex reads model + reasoning effort from `-c` config overrides (as args).
  export BUZZ_ACP_AGENT_ARGS="-c,model=\"${CODEX_MODEL}\",-c,model_reasoning_effort=\"${CODEX_EFFORT}\""
  MODEL_SHOWN="${CODEX_MODEL} effort=${CODEX_EFFORT}"
fi

# Delegation: obey the listed teammates. You (owner) are ALWAYS implicitly allowed.
allow="${!allow_var:-}"
if [ -n "${allow}" ]; then
  export BUZZ_ACP_RESPOND_TO="allowlist"
  export BUZZ_ACP_RESPOND_TO_ALLOWLIST="${allow}"
else
  export BUZZ_ACP_RESPOND_TO="owner-only"
fi

# Publish this agent's kind:0 profile so it shows up named, not as a raw pubkey.
# Idempotent (kind:0 is replaceable); non-fatal so a relay hiccup never blocks start.
buzz users set-profile --name "${NAME}" --about "${ABOUT}" \
  && echo "[run-agent] published profile: ${NAME}" \
  || echo "[run-agent] profile publish failed for ${NAME} (non-fatal)"

echo "[run-agent] role=${ROLE} runtime=${RUNTIME} model=${MODEL_SHOWN} agents=${BUZZ_ACP_AGENTS} prompt=${PROMPT} respond_to=${BUZZ_ACP_RESPOND_TO} auth_tag=${AUTHTAG_SHOWN}"
exec buzz-acp
