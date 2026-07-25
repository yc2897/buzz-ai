#!/usr/bin/env python3
"""Generate the 5 BUZZ_AUTH_TAG values (NIP-OA owner attestations).

Pure-Python BIP-340 Schnorr — no third-party packages.
Your owner private key is read via a hidden prompt (or the OWNER_KEY env var);
it is never written to disk, never passed as an argument, never printed.

Faithful to block/buzz  crates/buzz-sdk/src/nip_oa.rs:
    preimage = "nostr:agent-auth:" + agent_pubkey_hex + ":" + conditions
    message  = SHA256(preimage)
    sig      = BIP-340 Schnorr(message, owner_secret)
    tag      = ["auth", owner_pubkey_hex, conditions, sig_hex]
"""
import hashlib, os, getpass, sys, json

# ---- expected owner pubkey (x-only, hex) — sanity check the decoded secret ----
EXPECTED_OWNER = "a4753e3ba9c4c812a052dfe4e414e14469d3c60d09dbd07f76d3d70236445826"

# ---- the 5 agents: env-var name -> agent pubkey (hex) ----
AGENTS = [
    ("CAREER_AUTH_TAG",      "3dcfbb41070270812e49eb8eb92d2c31af7fe0de2740b66cdc430cfa0aae23ee"),
    ("OPERATIONS_AUTH_TAG",  "3d837d79bb1ec4e447410b8f10782f0d0c03f0eabed4813e91d2b76316136dd8"),
    ("KNOWLEDGE_AUTH_TAG",   "af2ca0a132be35ce28646ffb31a2a252aa3471d496d688b6a7469d4b802d0aa7"),
    ("REDTEAM_AUTH_TAG",     "1e63f11a00e41f021d319a97748d55445dae2bdec899f5093947e4c465f0317e"),
    ("ENGINEERING_AUTH_TAG", "0f6212cdd76e9aaa237f6b733ffa842da40dc502a22cbcf5eceb390ec691bb0e"),
]
CONDITIONS = ""  # empty = no expiry / no restrictions (matches every call site upstream)

# ===================== BIP-340 (secp256k1) reference math =====================
p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

def tagged_hash(tag, msg):
    t = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(t + t + msg).digest()

def point_add(P1, P2):
    if P1 is None: return P2
    if P2 is None: return P1
    if P1[0] == P2[0] and P1[1] != P2[1]: return None
    if P1 == P2:
        lam = (3 * P1[0] * P1[0] * pow(2 * P1[1], p - 2, p)) % p
    else:
        lam = ((P2[1] - P1[1]) * pow(P2[0] - P1[0], p - 2, p)) % p
    x3 = (lam * lam - P1[0] - P2[0]) % p
    return (x3, (lam * (P1[0] - x3) - P1[1]) % p)

def point_mul(P, k):
    R = None
    for i in range(256):
        if (k >> i) & 1:
            R = point_add(R, P)
        P = point_add(P, P)
    return R

def bytes_from_int(x): return x.to_bytes(32, "big")
def int_from_bytes(b): return int.from_bytes(b, "big")
def has_even_y(P): return P[1] % 2 == 0
def xor_bytes(a, b): return bytes(x ^ y for x, y in zip(a, b))

def lift_x(x):
    if x >= p: return None
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    if pow(y, 2, p) != y_sq: return None
    return (x, y if y % 2 == 0 else p - y)

def pubkey_xonly(seckey_int):
    P = point_mul(G, seckey_int)
    return bytes_from_int(P[0])

def schnorr_sign(msg32, seckey_int, aux=b"\x00" * 32):
    if not (1 <= seckey_int <= n - 1):
        raise ValueError("owner secret key out of range")
    P = point_mul(G, seckey_int)
    d = seckey_int if has_even_y(P) else n - seckey_int
    t = xor_bytes(bytes_from_int(d), tagged_hash("BIP0340/aux", aux))
    rand = tagged_hash("BIP0340/nonce", t + bytes_from_int(P[0]) + msg32)
    k0 = int_from_bytes(rand) % n
    if k0 == 0: raise ValueError("nonce is zero (retry)")
    R = point_mul(G, k0)
    k = k0 if has_even_y(R) else n - k0
    e = int_from_bytes(tagged_hash("BIP0340/challenge",
                                   bytes_from_int(R[0]) + bytes_from_int(P[0]) + msg32)) % n
    return bytes_from_int(R[0]) + bytes_from_int((k + e * d) % n)

def schnorr_verify(msg32, pubkey32, sig):
    P = lift_x(int_from_bytes(pubkey32))
    if P is None: return False
    r, s = int_from_bytes(sig[:32]), int_from_bytes(sig[32:])
    if r >= p or s >= n: return False
    e = int_from_bytes(tagged_hash("BIP0340/challenge", sig[:32] + pubkey32 + msg32)) % n
    R = point_add(point_mul(G, s), point_mul(P, n - e))
    return R is not None and has_even_y(R) and R[0] == r

# ===================== bech32 (nsec) decode =====================
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def bech32_decode(bech):
    bech = bech.strip()
    pos = bech.rfind("1")
    hrp, data = bech[:pos], bech[pos + 1:]
    dec = [CHARSET.find(c) for c in data]
    if any(d == -1 for d in dec): raise ValueError("bad bech32 char")
    return hrp, dec[:-6]  # drop 6-char checksum

def convertbits(data, frm, to):
    acc = bits = 0; out = []; maxv = (1 << to) - 1
    for v in data:
        acc = (acc << frm) | v; bits += frm
        while bits >= to:
            bits -= to; out.append((acc >> bits) & maxv)
    return out

def decode_owner_key(raw):
    raw = raw.strip()
    if raw.startswith("nsec1"):
        hrp, data = bech32_decode(raw)
        if hrp != "nsec": raise ValueError(f"expected nsec, got {hrp}")
        return bytes(convertbits(data, 5, 8))[:32]
    raw = raw.lower().removeprefix("0x")
    if len(raw) != 64: raise ValueError("hex secret must be 64 chars")
    return bytes.fromhex(raw)

# ===================== main =====================
HERE = os.path.dirname(os.path.abspath(__file__))

def _shred(path):
    """Overwrite then remove a file so the key doesn't linger on disk."""
    try:
        n = os.path.getsize(path)
        with open(path, "wb") as f:
            f.write(os.urandom(max(n, 64))); f.flush(); os.fsync(f.fileno())
    except OSError:
        pass
    try:
        os.remove(path)
    except OSError:
        pass

def read_owner_key():
    """Key source priority (all keep the value out of the chat transcript):
    1) OWNER_KEY env var
    2) key file (OWNER_KEY_FILE, or ./owner_key.local) — shredded after read
    3) interactive hidden prompt (only works with a real terminal)
    4) piped stdin (non-tty)
    """
    if os.environ.get("OWNER_KEY"):
        return os.environ["OWNER_KEY"]
    kf = os.environ.get("OWNER_KEY_FILE") or os.path.join(HERE, "owner_key.local")
    if os.path.exists(kf):
        with open(kf) as f:
            val = f.read().strip()
        _shred(kf)
        print(f"[ok] read owner key from {kf} and shredded it")
        return val
    try:
        return getpass.getpass("Owner private key (nsec or hex, hidden): ")
    except Exception:
        pass
    if not sys.stdin.isatty():
        line = sys.stdin.readline().strip()
        if line:
            return line
    sys.exit("No key provided. Create ./owner_key.local with your nsec, or pipe it via stdin.")

def main():
    raw = read_owner_key()
    try:
        sk = decode_owner_key(raw)
    finally:
        raw = None
    sk_int = int_from_bytes(sk)

    owner_hex = pubkey_xonly(sk_int).hex()
    if owner_hex != EXPECTED_OWNER:
        print(f"\n[FATAL] derived owner pubkey {owner_hex}\n"
              f"        does not match expected {EXPECTED_OWNER}\n"
              f"        -> wrong key. Nothing generated.", file=sys.stderr)
        sys.exit(1)
    print(f"[ok] owner key verified -> {owner_hex}\n")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_tags.local")
    # Restrict perms before writing any credential material.
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    lines = []
    for name, agent_hex in AGENTS:
        preimage = f"nostr:agent-auth:{agent_hex}:{CONDITIONS}"
        msg = hashlib.sha256(preimage.encode()).digest()
        sig = schnorr_sign(msg, sk_int)
        assert schnorr_verify(msg, bytes.fromhex(owner_hex), sig), f"self-verify FAILED for {name}"
        tag = json.dumps(["auth", owner_hex, CONDITIONS, sig.hex()], separators=(",", ":"))
        lines.append(f"{name}={tag}")
        # Masked confirmation only — full value stays out of the transcript.
        print(f"  {name:20s} OK  (self-verified)  sig={sig.hex()[:8]}…{sig.hex()[-4:]}")
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"\n[ok] all 5 signatures self-verified against BIP-340.")
    print(f"[ok] full values written to: {out_path}  (chmod 600)")
    print("     -> store each in Bitwarden as buzz_yc2897_agent_<slug>_auth_tag")
    print("        (the [\"auth\",…] array ONLY, no NAME= prefix), then delete this file.")

if __name__ == "__main__":
    main()
