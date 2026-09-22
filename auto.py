"""Auto-daemon buat Termux: jalan tiap ~20 menit lewat termux-job-scheduler,
cuma claim kalau: (1) udah lewat jam 07:00 WIB hari ini, (2) wallet itu belum
di-claim hari ini. Idempotent — aman dijalankan berulang.

Logika:
  - WIB = UTC+7, jadi jam 07:00 WIB = 00:00 UTC = window reset Merits.
  - "Hari ini" dihitung dari tanggal WIB (bukan UTC), biar konsisten.
  - Jitter 0-JITTER_MAX detik di tiap wallet, nghindarin thundering herd
    pas boundary 00:00 UTC.
  - State per-wallet disimpen di state.json (tanggal klaim terakhir).
  - Kalau token expired (401), dicek ulang di run berikutnya (user harus
    ambil rewards_api_token baru).

Jalankan manual:  python3 auto.py
Jadwalkan:       termux-job-scheduler --job-id 777 --period-ms 1200000 \
                 --task python3 $HOME/merits-bot/auto.py
"""
import os
import sys
import json
import time
import random
from datetime import datetime, timezone, timedelta

import claim as C

HERE = C.HERE
STATE_FILE = os.path.join(HERE, "state.json")
LOG_FILE = os.path.join(HERE, "claim.log")

WIB = timezone(timedelta(hours=7))
WINDOW_START_WIB = int(os.environ.get("MERITS_WINDOW_HOUR", "7"))  # jam WIB
JITTER_MAX = 180              # detik, random per wallet (0..180)
APPLY_JITTER = True           # set False buat test tanpa nunggu


def now_wib():
    return datetime.now(WIB)


def today_key():
    return now_wib().strftime("%Y-%m-%d")


def log(msg):
    ts = now_wib().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts} WIB] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, STATE_FILE)   # atomic — gak korup kalau dibunuh pas nulis


def in_window():
    """True kalau sekarang udah lewat jam 07:00 WIB."""
    return now_wib().hour >= WINDOW_START_WIB


def already_claimed_today(state, addr):
    return state.get(addr, {}).get("last_claim") == today_key()


def mark_claimed(state, addr):
    state.setdefault(addr, {})["last_claim"] = today_key()
    save_state(state)


# ---------- dry-run mode (test tanpa nyentuh API asli) ----------
DRY_RUN = os.environ.get("MERITS_DRY_RUN") == "1"
DRY_RUN_FAIL = os.environ.get("MERITS_DRY_RUN_FAIL") == "1"


def dry_claim(addr):
    time.sleep(0.05)
    if DRY_RUN_FAIL:
        return "error", "simulated failure"
    return "ok", f"+1 (dry-run) simulated for {addr[:10]}"


def run_wallet(label, token, state, stats):
    """Claim satu wallet kalau memenuhi syarat. Return True kalau beres."""
    addr = C.jwt_sub(token)
    tag = f"{label or addr[:10]} {addr}"

    if not in_window():
        log(f"[{tag}] SKIP: belum jam {WINDOW_START_WIB:02d}:00 WIB "
            f"(sekarang {now_wib().strftime('%H:%M')} WIB)")
        return False

    if already_claimed_today(state, addr):
        log(f"[{tag}] SKIP: udah claim hari ini ({today_key()})")
        return False

    if APPLY_JITTER and not DRY_RUN:
        j = random.randint(0, JITTER_MAX)
        log(f"[{tag}] jitter {j}s...")
        time.sleep(j)

    if DRY_RUN:
        st, info = dry_claim(addr)
    else:
        st, info = C.check_and_claim(tag, token)

    stats[st] = stats.get(st, 0) + 1

    bal = ""
    if st in ("ok", "skip") and not DRY_RUN:
        bal = f" {C.get_balance(token)}"

    if st == "ok":
        mark_claimed(state, addr)
        log(f"[{tag}] OK: {info}{bal}")
        return True
    if st == "skip":
        # server bilang udah claim — anggep beres, tandai biar gak ulang
        mark_claimed(state, addr)
        log(f"[{tag}] SKIP: {info}{bal}")
        return True
    if st == "expired":
        log(f"[{tag}] EXPIRED: {info} -> ambil rewards_api_token baru")
        return False
    log(f"[{tag}] ERROR: {info}")
    return False


def main():
    state = load_state()
    stats = {}

    token_rows = C.load_lines("tokens.txt")
    wallet_rows = C.load_lines("wallets.txt")
    env = os.environ.get("MERITS_TOKENS", "").strip()
    if env:
        token_rows = [C.parse_labeled_line(x)
                      for x in env.replace("\n", ",").split(",") if x.strip()]
        token_rows = [r for r in token_rows if r]

    if not token_rows and not wallet_rows:
        log("TIDAK ADA WALLET. Isi tokens.txt atau wallets.txt dulu.")
        return 1

    if not in_window():
        log(f"Belum jam {WINDOW_START_WIB:02d}:00 WIB "
            f"(sekarang {now_wib().strftime('%H:%M')} WIB). Tidur lagi.")
        return 0

    today = today_key()
    todo = [a for _, t in token_rows if (a := C.jwt_sub(t)) != "?"
            and state.get(a, {}).get("last_claim") != today]
    if todo:
        log(f"Run {today_key()} — {len(todo)} wallet menunggu claim, "
            f"{len(token_rows) + len(wallet_rows) - len(todo)} sudah selesai")

    n = 0
    for label, tok in token_rows:
        n += 1
        run_wallet(label or f"dompet{n}", tok, state, stats)

    # mode private-key: ambil token dari cache (login dilakuin claim.py biasa,
    # auto.py gak pegang private key buat alasan keamanan)
    for label, _ in wallet_rows:
        log(f"[{label or 'key'}] mode private-key: jalankan claim.py sekali "
            "buat login+cache, auto.py lanjut dari token cache")

    total = sum(stats.values())
    if total:
        log(f"RINGKASAN: " + " | ".join(
            f"{k}={v}" for k, v in sorted(stats.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
