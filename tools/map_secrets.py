#!/usr/bin/env python3
"""Project Bitwarden Secrets Manager names onto the env vars buzz-ai needs.

`bws` names secrets descriptively (`buzz_yc2897_agent_career_private`); the runtime
wants role-shaped names (`CAREER_NSEC`). This script is the adapter between them.

It reads the bws-named values from the ENVIRONMENT and writes NOTHING to disk.
Secret values only ever leave via stdout as shell-quoted exports — never in a log
line, an error message, or an argv.

Normally you don't run this directly: `start.py` imports `collect()` and passes the
result straight into the `docker compose` subprocess, so no shell is involved at all.

    python3 start.py --check          # the usual way to validate

Standalone use, if you want the vars in your own shell (note this leaves secrets in
that shell's environment, inherited by everything you run afterwards):

    while IFS=$'\t' read -r k v; do export "$k=$v"; done \
      < <(bws secret list "$BWS_PROJECT_ID" | jq -r '.[]|[.key,.value]|@tsv')
    eval "$(python3 tools/map_secrets.py)"

What it emits:

    BUZZ_ACP_AGENT_OWNER            <- buzz_yc2897_public_hex
    <ROLE>_NSEC                x5   <- buzz_yc2897_agent_<slug>_private
    <ROLE>_AUTH_TAG            x5   <- buzz_yc2897_agent_<slug>_auth_tag
    <ROLE>_ALLOWLIST           x5   <- DERIVED: the OTHER four agents' _public_hex
    CLAUDE_CODE_OAUTH_TOKEN         <- claude_oauth_token
    CODEX_AUTH_JSON                 <- base64(assembled ~/.codex/auth.json)

Beyond mapping, it verifies the things that fail confusingly at runtime:
  * each `*_private` really is the secret key for the stored `*_public_hex`
  * each `*_auth_tag` is a valid owner signature over THAT agent's pubkey
Both catch a half-finished key rotation before the relay silently rejects an agent.
"""
import base64
import hashlib
import json
import os
import shlex
import sys

# The BIP-340 / bech32 math already lives next door; don't reimplement it.
# gen_auth_tags.py only runs main() under __main__, so importing is side-effect free.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_auth_tags import (  # noqa: E402
    decode_owner_key as decode_secret_key,  # accepts nsec1… or 64-char hex
    int_from_bytes,
    pubkey_xonly,
    schnorr_verify,
)

# role env prefix -> the slug Bitwarden uses in buzz_yc2897_agent_<slug>_*
# NOTE the spelling drift: bws says `operation`/`red_team`, the code wants
# OPERATIONS/REDTEAM. That mismatch is the reason this table exists.
ROLES = [
    ("CAREER", "career"),
    ("OPERATIONS", "operation"),
    ("KNOWLEDGE", "knowledge"),
    ("REDTEAM", "red_team"),
    ("ENGINEERING", "engineering"),
]

PREFIX = "buzz_yc2897"
# The owner's x-only pubkey, hex. The matching `_public_npub` is the same key in
# bech32 — buzz wants hex here, so the npub entry is unused by this script.
OWNER_PUBKEY_SECRET = f"{PREFIX}_public_hex"
CLAUDE_TOKEN_SECRET = "claude_oauth_token"

# codex_* pieces -> where they land in ~/.codex/auth.json
# (shape from templates/codex-auth.example.json)
CODEX_TOKEN_FIELDS = {
    "codex_id_token": "id_token",
    "codex_access_token": "access_token",
    "codex_refresh_token": "refresh_token",
    "codex_account_id": "account_id",
}
CODEX_LAST_REFRESH = "codex_last_refresh"

problems: list[str] = []


def fail(msg: str) -> None:
    """Record a problem. Never include a secret VALUE in msg — names only."""
    problems.append(msg)


def get(name: str) -> str | None:
    """Read one bws-named secret from the environment. Blank counts as missing."""
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"missing secret: {name}")
        return None
    return value


def is_hex64(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def check_keypair(role: str, nsec: str, pub_hex: str) -> None:
    """Confirm the private key actually derives the stored public key."""
    try:
        derived = pubkey_xonly(int_from_bytes(decode_secret_key(nsec))).hex()
    except Exception as e:  # noqa: BLE001 - message must not echo the key
        fail(f"{role}: could not decode {PREFIX}_agent_* private key ({type(e).__name__})")
        return
    if derived != pub_hex.lower():
        fail(
            f"{role}: private key does not match its stored public key "
            f"(derived {derived[:8]}…, stored {pub_hex[:8]}…) — mid-rotation mismatch?"
        )


def check_auth_tag(role: str, tag_json: str, agent_hex: str, owner_hex: str) -> None:
    """Confirm the tag is a valid owner attestation for THIS agent's pubkey."""
    try:
        tag = json.loads(tag_json)
    except json.JSONDecodeError as e:
        # Show the shape, not the value. A correct tag starts `["auth","<owner
        # pubkey>` — all public — so a short prefix is safe to print and is
        # usually enough to spot the mistake.
        hint = ""
        if "=" in tag_json[:32] and tag_json.lstrip().startswith(tuple(f"{r}_" for r, _ in ROLES)):
            hint = (
                " — looks like a whole line from tools/auth_tags.local; store ONLY"
                ' the ["auth",…] part, without the NAME= prefix'
            )
        elif tag_json.count('["auth"') > 1:
            hint = " — more than one tag in this secret; store exactly one"
        fail(
            f"{role}_AUTH_TAG is not valid JSON ({e.msg}); "
            f"len={len(tag_json)}, starts {tag_json[:14]!r}{hint}"
        )
        return
    if not (isinstance(tag, list) and len(tag) == 4 and tag[0] == "auth"):
        fail(f'{role}_AUTH_TAG must be ["auth",<owner>,<conditions>,<sig>]')
        return
    _, tag_owner, conditions, sig_hex = tag
    if tag_owner.lower() != owner_hex.lower():
        fail(
            f"{role}_AUTH_TAG was signed by a different owner "
            f"({tag_owner[:8]}… vs {owner_hex[:8]}…) — stale after an owner-key rotation?"
        )
        return
    if not (len(sig_hex) == 128 and is_hex64(sig_hex[:64]) and is_hex64(sig_hex[64:])):
        fail(f"{role}_AUTH_TAG signature is not 128 hex chars")
        return
    # Same preimage as block/buzz crates/buzz-sdk/src/nip_oa.rs.
    msg = hashlib.sha256(f"nostr:agent-auth:{agent_hex}:{conditions}".encode()).digest()
    try:
        ok = schnorr_verify(msg, bytes.fromhex(owner_hex), bytes.fromhex(sig_hex))
    except Exception as e:  # noqa: BLE001
        fail(f"{role}_AUTH_TAG signature could not be checked ({type(e).__name__})")
        return
    if not ok:
        fail(
            f"{role}_AUTH_TAG is not a valid signature over this agent's pubkey "
            f"({agent_hex[:8]}…) — re-mint with tools/gen_auth_tags.py"
        )


def build_codex_auth_json() -> str | None:
    """Reassemble ~/.codex/auth.json from its 5 parts, then base64 it.

    run-agent.sh does `printf '%s' "$CODEX_AUTH_JSON" | base64 -d > auth.json`,
    so this must be single-line standard base64.
    """
    tokens = {}
    for secret_name, field in CODEX_TOKEN_FIELDS.items():
        value = get(secret_name)
        if value is None:
            return None
        tokens[field] = value
    last_refresh = get(CODEX_LAST_REFRESH)
    if last_refresh is None:
        return None
    auth = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": tokens,
        "last_refresh": last_refresh,
    }
    return base64.b64encode(json.dumps(auth).encode()).decode()


def collect() -> tuple[list[tuple[str, str]], list[str]]:
    """Build the (env-var, value) pairs from the bws-named vars in os.environ.

    Returns (exports, problems). `exports` is only trustworthy when `problems`
    is empty — callers must check. Importable so start.py can reuse the mapping
    and validation without going through a shell.
    """
    global problems
    problems = []
    exports: list[tuple[str, str]] = []

    owner_hex = get(OWNER_PUBKEY_SECRET)
    if owner_hex and not is_hex64(owner_hex):
        fail(f"{OWNER_PUBKEY_SECRET} must be 64-char hex (an npub won't work here)")
        owner_hex = None
    if owner_hex:
        exports.append(("BUZZ_ACP_AGENT_OWNER", owner_hex.lower()))

    # Pass 1: collect per-role material and validate it.
    pubkeys: dict[str, str] = {}
    for role, slug in ROLES:
        base = f"{PREFIX}_agent_{slug}"
        nsec = get(f"{base}_private")
        pub_hex = get(f"{base}_public_hex")
        tag = get(f"{base}_auth_tag")

        if pub_hex and not is_hex64(pub_hex):
            fail(f"{base}_public_hex must be 64-char hex (use the _hex, not the _npub)")
            pub_hex = None
        if pub_hex:
            pubkeys[role] = pub_hex.lower()
        if nsec and pub_hex:
            check_keypair(role, nsec, pub_hex)
        if tag and pub_hex and owner_hex:
            check_auth_tag(role, tag, pub_hex.lower(), owner_hex)

        if nsec:
            exports.append((f"{role}_NSEC", nsec))
        if tag:
            exports.append((f"{role}_AUTH_TAG", tag))

    # Pass 2: full mesh — each agent's allowlist is the OTHER four pubkeys.
    # Never its own; you (owner) are implicitly allowed and never listed.
    if len(pubkeys) == len(ROLES):
        for role, _ in ROLES:
            others = [pubkeys[r] for r, _ in ROLES if r != role]
            exports.append((f"{role}_ALLOWLIST", ",".join(others)))

    claude = get(CLAUDE_TOKEN_SECRET)
    if claude:
        exports.append(("CLAUDE_CODE_OAUTH_TOKEN", claude))

    codex = build_codex_auth_json()
    if codex:
        exports.append(("CODEX_AUTH_JSON", codex))

    return exports, problems


def report_problems(problems: list[str]) -> None:
    """Print the problem list (names only, never values) to stderr."""
    print(f"[map_secrets] {len(problems)} problem(s) — nothing exported:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    if any("_auth_tag" in p for p in problems):
        print(
            "\n  The 5 auth tags must be minted on this Mac (they need your OWNER\n"
            "  PRIVATE key — public keys cannot produce one) and then stored in\n"
            "  Bitwarden as:\n"
            + "".join(f"    {PREFIX}_agent_{slug}_auth_tag\n" for _, slug in ROLES)
            + "  Mint them with:  python3 tools/gen_auth_tags.py",
            file=sys.stderr,
        )


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    exports, problems = collect()

    if problems:
        report_problems(problems)
        return 1

    if check_only:
        print(
            f"[map_secrets] OK — {len(exports)} vars ready "
            "(keypairs match, auth tags verify against the owner pubkey)",
            file=sys.stderr,
        )
        for name, value in exports:
            print(f"  {name:24s} len={len(value)}", file=sys.stderr)
        return 0

    # stdout is consumed by `eval` — quote so values with quotes/commas/spaces survive.
    for name, value in exports:
        print(f"export {name}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
