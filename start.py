#!/usr/bin/env python3
"""Start the buzz-ai agents. Works identically on macOS, Linux and Windows.

    python3 start.py            # fetch secrets -> validate -> compose up -d --build
    python3 start.py --check    # validate only, print nothing secret, don't start
    python3 start.py --down     # docker compose down
    python3 start.py --no-build # start without rebuilding the image first

This is the only entry point, and the same command works everywhere — PowerShell,
cmd, WSL, macOS Terminal, Linux. There is deliberately no start.sh: a .sh checked
out with CRLF cannot run at all, because the kernel looks for an interpreter
literally named "bash\\r" and fails before the first line executes, so no guard
inside it could ever help. Python's parser accepts either line ending, which
makes this file immune to that whole class of problem.

Prefer `python3 start.py` over `./start.py`. Both work on Unix, but the explicit
form also survives a CRLF checkout — this file's shebang is exactly as fragile as
any other script's.

Why Python rather than shell, concretely:
  * no CRLF fragility (above)
  * no `jq` dependency — we parse bws's JSON natively
  * no `eval` of generated shell — secrets go straight from bws into the
    docker subprocess's environment, so they never touch a shell command line,
    your shell history, or the environment of anything else you run afterwards

Prereqs: docker, bws (Bitwarden Secrets Manager CLI), python3 >= 3.9.
Bootstrap env (keep out of git — shell profile or OS keychain):
    BWS_ACCESS_TOKEN   machine-account token, read access to the project
    BWS_PROJECT_ID     the Secrets Manager project holding the secrets

NEVER pass BWS_ACCESS_TOKEN into the container: the agents run unsandboxed as a
single UID and would read it, then fetch every secret. bws runs here, on the
host, and the container receives only finished values.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))

# Resolved at runtime via the sys.path line above, so static analysers can't see it.
import map_secrets  # noqa: E402  # type: ignore[import-not-found]


def die(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    print(f"[start] {msg}", file=sys.stderr)
    raise SystemExit(1)


def require_tools(*names: str) -> dict[str, str]:
    """Resolve each executable, or explain what's missing. bws may be un-PATHed."""
    found = {}
    for n in names:
        p = shutil.which(n)
        if p is None and n == "bws":
            # Common case: downloaded but not installed to PATH.
            for cand in (
                os.path.expanduser("~/Downloads/bws"),
                os.path.expanduser("~/.local/bin/bws"),
                os.path.join(HERE, "bws"),
            ):
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    p = cand
                    break
        if p is None:
            die(f"missing dependency: {n} (not on PATH)")
        found[n] = p
    return found


def fetch_secrets(bws: str, project_id: str) -> dict[str, str]:
    """`bws secret list` -> {key: value}. JSON parsed natively; no jq, no shell."""
    proc = subprocess.run(
        [bws, "secret", "list", project_id],
        capture_output=True,
        text=True,
        # token passed via env, never as an argv element (argv is world-readable in ps)
        env={**os.environ},
    )
    if proc.returncode != 0:
        # bws puts auth failures on stderr; surface it but don't echo the token.
        die(f"bws failed (exit {proc.returncode}): {proc.stderr.strip()[:400]}")
    try:
        items = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        die(f"could not parse bws output as JSON: {e.msg}")
    secrets = {i["key"]: i["value"] for i in items if i.get("key")}
    if not secrets:
        die(f"bws returned no secrets for project {project_id}")
    return secrets


def compose(*args: str, env: dict[str, str] | None = None) -> int:
    """Run `docker compose ...` from the repo dir with an explicit environment."""
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=HERE,
        env=env if env is not None else {**os.environ},
    ).returncode


def main(argv: list[str]) -> int:
    if "--down" in argv:
        print("[start] stopping…")
        return compose("down")

    check_only = "--check" in argv

    token = os.environ.get("BWS_ACCESS_TOKEN", "").strip()
    project = os.environ.get("BWS_PROJECT_ID", "").strip()
    if not token:
        die("set BWS_ACCESS_TOKEN (Bitwarden Secrets Manager machine token)")
    if not project:
        die("set BWS_PROJECT_ID (the project holding the secrets)")

    tools = require_tools("docker", "bws")

    print("[start] fetching secrets from Bitwarden Secrets Manager…")
    secrets = fetch_secrets(tools["bws"], project)
    print(f"[start] loaded {len(secrets)} secrets (in memory only — nothing on disk)")

    # map_secrets reads the bws-named values from os.environ, validates every
    # keypair and auth tag, and returns the role-shaped names the runtime wants.
    os.environ.update(secrets)
    print("[start] mapping Bitwarden names -> runtime env vars…")
    exports, problems = map_secrets.collect()
    if problems:
        map_secrets.report_problems(problems)
        die("secret mapping failed (see above) — not starting anything")

    if check_only:
        print(
            f"[start] OK — {len(exports)} vars ready "
            "(keypairs match, auth tags verify against the owner pubkey)"
        )
        for name, value in exports:
            print(f"  {name:24s} len={len(value)}")
        return 0

    # Build the child environment explicitly. The bws-named originals are dropped:
    # compose only passes through the role-shaped names, and BWS_ACCESS_TOKEN must
    # never reach the container.
    child = {k: v for k, v in os.environ.items() if k not in secrets}
    child.pop("BWS_ACCESS_TOKEN", None)
    child.update(dict(exports))

    # Build by default. `compose up` on its own only builds when the image is
    # MISSING, so once buzz-ai:local exists every later edit to the Dockerfile,
    # prompts, skills or run-agent.sh is silently ignored — you restart, see no
    # change, and go looking for the bug in the wrong place. A no-op rebuild costs
    # about a second because every layer is cached, so this is close to free.
    # --no-build opts out for the rare case where you want the image left alone.
    up = ["up", "-d"] + ([] if "--no-build" in argv else ["--build"])
    print(f"[start] starting {len(exports)} vars -> docker compose {' '.join(up)}")
    rc = compose(*up, env=child)
    if rc == 0:
        print("[start] up. Logs:  docker compose logs -f")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
