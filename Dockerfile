# Buzz agents image — 5 Claude Code agents under one supervisor.
#
# One container runs this image. Inside it, `supervisord` (the
# "keep-everything-running" program) launches all 5 agents and restarts any
# that crash. Docker only watches supervisord; supervisord watches the agents.
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
        ca-certificates git openssl bash supervisor python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    # Debian 12 ships python3 as PEP 668 "externally managed", which makes even
    # `pip install --user` fail outright — the agents' prompts promise that it
    # works, so without this they'd be lied to. Dropping the marker is safe here
    # in a way it wouldn't be on a real machine: this image exists only to run
    # the agents, there are no distro Python packages to break, and the agents
    # are uid 1001, so a bare `pip install` still can't touch /usr. Installs go
    # to /home/agent/.local, which is the persistent volume.
    && rm -f /usr/lib/python3.11/EXTERNALLY-MANAGED

# ACP adapters — Claude Code (career/operations/knowledge) + Codex (redteam/engineering).
RUN npm install -g @agentclientprotocol/claude-agent-acp @agentclientprotocol/codex-acp

# The two Buzz binaries.
COPY --from=builder /src/target/release/buzz-acp /usr/local/bin/buzz-acp
COPY --from=builder /src/target/release/buzz     /usr/local/bin/buzz

# Per-agent system prompts (one .md per role), launcher, and supervisor config.
COPY prompts          /opt/buzz-prompts
COPY run-agent.sh     /usr/local/bin/run-agent.sh
COPY supervisord.conf /etc/supervisor/agents.conf
# Vendored skills (see skills/README.md). Kept OUT of /home/agent on purpose: that
# path is a named volume, and a volume only seeds from the image the first time it
# is created — after that, image updates would be invisible. run-agent.sh copies
# the per-role subset in at every start instead, so the image stays authoritative.
COPY skills           /opt/buzz-skills
# Normalize line endings: a Windows checkout copies these as CRLF, which breaks
# the bash shebang and the supervisord parser. Strip CR so the image is correct
# regardless of the host that built it.
RUN sed -i 's/\r$//' /usr/local/bin/run-agent.sh /etc/supervisor/agents.conf \
    && chmod +x /usr/local/bin/run-agent.sh \
    && useradd --create-home --shell /bin/bash agent

# Run as non-root. Each agent has full access to THIS container's filesystem,
# so keep nothing sensitive baked into the image.
USER agent
WORKDIR /home/agent

# `pip install --user` puts console scripts in ~/.local/bin. Without this on PATH
# the library imports but the command it ships is "not found", which reads as a
# broken install rather than a missing PATH entry.
ENV PATH="/home/agent/.local/bin:${PATH}"

# The ONE program the container runs. supervisord starts + babysits the 5 agents.
CMD ["supervisord", "-c", "/etc/supervisor/agents.conf"]
