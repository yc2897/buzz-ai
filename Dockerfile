# Buzz agents image — 5 Claude Code agents under one supervisor.
#
# One DigitalOcean Worker runs this image. Inside it, `supervisord` (the
# "keep-everything-running" program) launches all 5 agents and restarts any
# that crash. DO only watches supervisord; supervisord watches the agents.
#
# Only two upstream crates are built (buzz-acp = harness, buzz = the CLI the
# agent uses to post/read). Everything else (the relay) is hosted by Block.
# Upstream is cloned from a PINNED tag, so this repo stays tiny and private.

# ─── Stage 1: build the two Rust binaries from pinned upstream ──────────────
FROM rust:1.95-bookworm AS builder

# Bump this (only this) to take official Buzz updates. Use a tag, never `main`.
ARG BUZZ_REF=v0.4.22

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential pkg-config libssl-dev ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch "${BUZZ_REF}" https://github.com/block/buzz.git .
RUN cargo build --release --locked -p buzz-acp -p buzz-cli \
    && strip target/release/buzz-acp target/release/buzz

# ─── Stage 2: runtime ───────────────────────────────────────────────────────
# Node base because the Claude Code adapter is an npm package.
FROM node:24-bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates git openssl bash supervisor \
    && rm -rf /var/lib/apt/lists/*

# ACP adapters — Claude Code (career/operations/knowledge) + Codex (redteam/engineering).
RUN npm install -g @agentclientprotocol/claude-agent-acp @agentclientprotocol/codex-acp

# The two Buzz binaries.
COPY --from=builder /src/target/release/buzz-acp /usr/local/bin/buzz-acp
COPY --from=builder /src/target/release/buzz     /usr/local/bin/buzz

# Per-agent system prompts (one .md per role), launcher, and supervisor config.
COPY prompts          /opt/buzz-prompts
COPY run-agent.sh     /usr/local/bin/run-agent.sh
COPY supervisord.conf /etc/supervisor/agents.conf
RUN chmod +x /usr/local/bin/run-agent.sh \
    && useradd --create-home --shell /bin/bash agent

# Run as non-root. Each agent has full access to THIS container's filesystem,
# so keep nothing sensitive baked into the image.
USER agent
WORKDIR /home/agent

# The ONE program DO runs. supervisord then starts + babysits the 5 agents.
CMD ["supervisord", "-c", "/etc/supervisor/agents.conf"]
