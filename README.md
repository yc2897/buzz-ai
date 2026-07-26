# buzz-ai

Five personal AI agents that run always-on in Docker on your own machine, talking to a
Block-hosted Buzz relay. You reach them from the Buzz app — phone or desktop — the same way
you'd message a colleague.

```
You (CEO) ─ human
├── Career        (Claude Code · claude-opus-4-8)
├── Operations    (Claude Code · claude-opus-4-8)
├── Knowledge     (Claude Code · claude-opus-4-8)
├── Red Team      (Codex · gpt-5.5)
└── Engineering   (Codex · gpt-5.5)
```

Flat by design: all five report to you, none outranks another, and every agent can
@mention every other. No cloud deployment — it runs on a machine you already own, on the
Claude and ChatGPT subscriptions you already pay for.

## Start here

| I want to… | Go to |
|---|---|
| **Run it** — start, stop, back up, update | **[docs/operating.md](docs/operating.md)** |
| **Fix something** — an agent is silent, auth broke | **[docs/troubleshooting.md](docs/troubleshooting.md)** |
| **Understand it** — design, layout, why it's like this | **[docs/architecture.md](docs/architecture.md)** |
| **Rare surgery** — rotate keys, restore a backup | **[docs/runbooks.md](docs/runbooks.md)** |

## The commands you'll actually type

```bash
python3 start.py            # start  (same on macOS, Linux, Windows)
python3 start.py --check    # validate every secret, start nothing
python3 start.py --down     # stop

docker compose logs -f              # watch
docker compose exec backup backup   # back up now, instead of waiting for 03:00
```

Needs `docker`, `bws` (Bitwarden Secrets Manager CLI) and `python3`, plus
`BWS_ACCESS_TOKEN` and `BWS_PROJECT_ID` in your shell. The first run builds the image,
which takes a few minutes. Full detail in **[operating.md](docs/operating.md)**.

## How it hangs together

```
your machine
└── docker container
    └── supervisord ──┬── career / operations / knowledge  → claude-agent-acp
                      └── redteam / engineering            → codex-acp
        all five dial OUT to wss://yc2897.communities.buzz.xyz

    /home/agent  ← persistent volume; each agent works in work/<ROLE>
    backup sidecar → stops the container nightly, archives it, restarts it
```

Secrets live in Bitwarden and are injected at runtime by `start.py` — never written to
disk, never baked into the image, never committed. The Buzz desktop app is only a
*client*: the agents run whether or not it's open.

## Upstream

Buzz source isn't vendored here. The `Dockerfile` clones a pinned tag (`v0.4.22`) from
[block/buzz](https://github.com/block/buzz) at build time, so taking updates means bumping
one tag. Never point it at `main`.

Cloud was tried and dropped: at 512 MB the container crash-looped, and a stable ≥2 GB
instance costs real money monthly. If you ever want it back, recover `app.yaml` from git
history rather than rewriting it.
