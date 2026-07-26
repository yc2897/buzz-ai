# Running it day to day

The commands you actually type. Start, stop, back up, update.

> Part of **buzz-ai** — see [README](../README.md) for the map.

## Starting and stopping

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

### macOS, Linux, Windows

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

## Backups

The `backup` sidecar ([offen/docker-volume-backup](https://offen.github.io/docker-volume-backup/))
runs nightly at 03:00: it **stops `agents`, archives the volume, restarts it**, then prunes
archives older than 14 days into `./backups/` (git-ignored).

Stopping first is the point. Archiving a live filesystem gives a torn result — a file
written mid-read lands in the tarball half-old and half-new, and Codex's SQLite state under
`~/.codex-<ROLE>` corrupts exactly that way. Worth knowing that **busybox `tar` doesn't even
warn**: it exits 0 on a changed file and writes a broken archive, so a hand-rolled
`alpine`-based backup would fail silently. GNU tar at least exits 1.

Credentials never enter an archive — `BACKUP_EXCLUDE_REGEXP` drops `auth.json`,
`credentials.json` and `.bash_history`, plus `node_modules`/venvs/caches, which are
regenerable and would bloat every run.

**To ship offsite**, set `AGE_PASSPHRASE` in your shell (it passes through) and uncomment
the `AWS_*` block — it also speaks WebDAV, Azure Blob, Dropbox, Google Drive and SSH.
Encrypt first: the archive still holds everything your agents were working on.


> ⚠️ The sidecar mounts the **Docker socket**, which is Docker's control API — anything
> that can talk to it can ask Docker to start a privileged container, so it amounts to root
> on the Docker VM (not on macOS; the LinuxKit VM is a second boundary). It's given to the
> sidecar and *not* to `agents`, and the sidecar exposes no ports, so your agents can't
> reach it. Pin the tag and treat a version bump as a trust decision. The socket is mounted
> `:ro` to match the upstream recipe, but that is not a boundary — talking to a socket isn't
> a file write, so read-only still permits the whole API.

## Taking upstream updates
Bump `BUZZ_REF` (the `Dockerfile` `ARG`) from `v0.4.22` to a newer **tag**, then
`docker compose build && python3 start.py`. Never point at `main`.
