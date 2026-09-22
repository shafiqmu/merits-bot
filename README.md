# Blockscout Merits Daily Claim Bot

Auto-claim daily merits buat banyak wallet. Python stdlib only (tanpa `pip install`).

## Setup

```sh
cp tokens.example.txt tokens.txt
# isi tokens.txt: label|JWT  (satu per baris)
nano tokens.txt
python3 claim.py
```

Token: login di https://eth.blockscout.com/account/merits, DevTools > Network >
request ke `merits.blockscout.com` > header `Authorization: Bearer ...`.

## Otomatis harian

- Windows: Task Scheduler → `run.bat` tiap hari 07:05 WIB
- Termux/Linux: cron → `sh run.sh`, atau `5 7 * * * cd ~/merits-bot && python3 claim.py >> claim.log 2>&1`

## File

| File | Keterangan |
|---|---|
| `claim.py` | bot (check → claim → balance) |
| `auto.py` | mode Termux: state-gated, jalan tiap ~20 menit |
| `tokens.txt` | JWT per wallet — **JANGAN commit** (di `.gitignore`) |
| `wallets.txt` | opsional mode private-key, butuh `pip install eth-account` |
| `state.json` | tanggal klaim terakhir per wallet (auto, di-gitignore) |
| `run.bat` / `run.sh` | launcher Windows / Linux |

## Mode Termux (otomatis di HP)

`auto.py` cek tiap kali dijalankan: kalau **sudah lewat jam 07:00 WIB** dan
wallet itu **belum klaim hari ini**, baru klaim. Aman dijalankan berulang
(idempotent) — Android yang bangunin lewat JobScheduler, bukan daemon.

**Setup:**

1. Install **Termux:API** (F-Droid) → buka sekali → izinkan permission
2. Settings → Apps → Termux:API → Battery → **Unrestricted**
3. `pkg install termux-api -y`
4. Isi `tokens.txt` seperti biasa
5. Daftar jadwal:

```sh
termux-job-scheduler --job-id 777 --period-ms 1200000 \
  --task "python3 $HOME/merits-bot/auto.py"
```

`--period-ms 1200000` = tiap 20 menit. Android bisa tunda jadi ~25-35 menit
tergantung baterai — tidak masalah, window claim ~24 jam.

Cek jadwal: `termux-job-scheduler -p` · berhenti: `termux-job-scheduler -c`

**Test tanpa nyentuh API asli:**

```sh
MERITS_DRY_RUN=1 MERITS_WINDOW_HOUR=1 python3 auto.py
```

`MERITS_WINDOW_HOUR` bisa dipakai untuk menggeser jam mulai (default `7`).

## Output

```
[dompet1 0x396a...] SKIP: streak=1 reset=2026-09-12T00:00:00.000Z bal=3010
RINGKASAN: 0 claim | 1 skip | 0 expired | 0 error
```
