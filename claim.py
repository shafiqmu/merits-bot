"""Blockscout Merits daily-claim bot — multi-wallet.
Mode 1 (simpel): tokens.txt -> satu JWT per baris, format: label|jwt  ATAU  label=jwt  ATAU  bare-jwt
Mode 2 (private-key): wallets.txt -> satu key per baris, format: label|0xKEY. Bot auto-login (nonce->sign->login) + cache token.
Jalankan: python claim.py
"""
import os, sys, json, base64, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://merits.blockscout.com"
HOST = "eth.blockscout.com"
ORIGIN = f"https://{HOST}"
CHAIN_ID = 1
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
CACHE = os.path.join(HERE, "tokens_cache.json")

def req_json(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    r.add_header("accept", "*/*")
    r.add_header("origin", ORIGIN)
    r.add_header("referer", ORIGIN + "/")
    r.add_header("user-agent", UA)
    if token:
        r.add_header("authorization", f"Bearer {token}")
    if body is not None:
        r.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            b = e.read().decode()
        except Exception:
            b = ""
        try:
            return e.code, json.loads(b or "{}")
        except Exception:
            return e.code, {"_raw": b}

def b64url_decode(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)

def jwt_sub(tok):
    try:
        return json.loads(b64url_decode(tok.split(".")[1]).decode()).get("sub", "?")
    except Exception:
        return "?"

def mask(s, a=8, b=6):
    s = s.strip()
    return (s[:a] + "..." + s[-b:]) if len(s) > a + b + 3 else "***"

def parse_labeled_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    for sep in ("|", "=", ":"):
        if sep in line:
            label, val = line.split(sep, 1)
            label, val = label.strip(), val.strip()
            if label and val:
                return label, val
    return None, line  # bare value, label nyusul

def load_lines(fname):
    p = os.path.join(HERE, fname)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        r = parse_labeled_line(line)
        if r:
            out.append(r)
    return out

def load_cache():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE, "w", encoding="utf-8"), indent=1)

def iso_now_plus(years=0):
    now = datetime.now(timezone.utc)
    s = lambda d: d.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    exp = now + timedelta(days=365 * years) if years else now
    return s(now), s(exp)

def build_message(address, nonce, exists, ref=""):
    issued, exp = iso_now_plus(1)
    if exists:
        line3 = "Sign-In for the Blockscout Merits program."
    else:
        line3 = "Sign-Up for the Blockscout Merits program. I accept Terms of Service: https://merits.blockscout.com/terms. I love capybaras." + (f" Referral code: {ref}" if ref else "")
    return "\n".join([
        f"{HOST} wants you to sign in with your Ethereum account:",
        address, "", line3, "",
        f"URI: {ORIGIN}", "Version: 1", f"Chain ID: {CHAIN_ID}",
        f"Nonce: {nonce}", f"Issued At: {issued}", f"Expiration Time: {exp}",
    ])

def login_with_key(pk_hex, ref=""):
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.from_key(pk_hex)
    address = acct.address
    sc, n = req_json("GET", "/api/v1/auth/nonce")
    if sc != 200 or "nonce" not in n:
        return None, f"nonce gagal {sc}: {n}"
    nonce = n["nonce"]
    sc2, u = req_json("GET", f"/api/v1/auth/user/{address}")
    exists = bool(u.get("exists")) if sc2 == 200 else True
    msg = build_message(address, nonce, exists, ref)
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    sc3, res = req_json("POST", "/api/v1/auth/login",
                        body={"nonce": nonce, "message": msg, "signature": sig})
    if sc3 != 200 or "token" not in res:
        return None, f"login gagal {sc3}: {res}"
    return res["token"], None

def check_and_claim(label, token):
    sc, c = req_json("GET", "/api/v1/user/daily/check", token=token)
    if sc == 401:
        return "expired", None
    if sc != 200:
        return "error", f"check {sc}: {c}"
    if not c.get("available"):
        return "skip", f"streak={c.get('streak')} reset={c.get('reset_at')}"
    sc2, r = req_json("POST", "/api/v1/user/daily/claim", token=token, body={})
    if sc2 == 200:
        return "ok", f"+{r.get('total_reward')} streak={r.get('streak')}"
    if sc2 == 400 and "already" in json.dumps(r).lower():
        return "skip", f"sudah claim ({r})"
    return "error", f"claim {sc2}: {r}"

def get_balance(token):
    try:
        sc, b = req_json("GET", "/api/v1/user/balances", token=token)
        if sc == 200 and "total" in b:
            return f"bal={b.get('total')}"
    except Exception:
        pass
    return ""

def main():
    token_rows = load_lines("tokens.txt")
    wallet_rows = load_lines("wallets.txt")
    # env override: MERITS_TOKENS="label|jwt, label2|jwt2" atau bare jwt koma/newline
    env = os.environ.get("MERITS_TOKENS", "").strip()
    if env:
        token_rows = [parse_labeled_line(x) for x in env.replace("\n", ",").split(",") if x.strip()]
        token_rows = [r for r in token_rows if r]
    if not token_rows and not wallet_rows:
        print("TIDAK ADA WALLET. Isi tokens.txt (JWT) atau wallets.txt (private key). Lihat contoh di bawah:")
        print("  tokens.txt : dompet1|<JWT-rewards_api_token>")
        print("  wallets.txt: dompet1|0xabc...  (jangan share file ini)")
        return 1
    cache = load_cache()
    stats = {"ok": 0, "skip": 0, "error": 0, "expired": 0}
    n = 0
    # --- mode JWT ---
    for label, tok in token_rows:
        n += 1
        addr = jwt_sub(tok)
        tag = f"{label or 'dompet'+str(n)} {addr}"
        st, info = check_and_claim(tag, tok)
        stats[st] = stats.get(st, 0) + 1
        bal = f" {get_balance(tok)}" if st in ("ok", "skip") else ""
        print(f"[{tag}] {st.upper()}: {info}{bal}" + (" -> ambil rewards_api_token baru" if st == "expired" else ""))
    # --- mode private-key ---
    for label, pk in wallet_rows:
        n += 1
        pk = pk.strip()
        try:
            from eth_account import Account
            addr = Account.from_key(pk).address
        except Exception as e:
            stats["error"] += 1
            print(f"[{label or 'key'+str(n)}] ERROR: private key invalid ({e})")
            continue
        tag = f"{label or addr[:10]} {addr}"
        tok = (cache.get(addr) or {}).get("token")
        if tok:
            st, info = check_and_claim(tag, tok)
            if st != "expired":
                stats[st] = stats.get(st, 0) + 1
                bal = f" {get_balance(tok)}" if st in ("ok", "skip") else ""
                print(f"[{tag}] {st.upper()}: {info}{bal} (cache)")
                continue
        tok, err = login_with_key(pk)
        if err:
            stats["error"] += 1
            print(f"[{tag}] ERROR: {err}")
            continue
        cache[addr] = {"token": tok, "updated_at": datetime.now(timezone.utc).isoformat()}
        save_cache(cache)
        st, info = check_and_claim(tag, tok)
        stats[st] = stats.get(st, 0) + 1
        bal = f" {get_balance(tok)}" if st in ("ok", "skip") else ""
        print(f"[{tag}] {st.upper()}: {info}{bal} (login baru)")
    print(f"RINGKASAN: {stats.get('ok',0)} claim | {stats.get('skip',0)} skip | {stats.get('expired',0)} expired | {stats.get('error',0)} error")
    return 0

if __name__ == "__main__":
    sys.exit(main())
