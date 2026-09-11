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
| `tokens.txt` | JWT per wallet — **JANGAN commit** (di `.gitignore`) |
| `wallets.txt` | opsional mode private-key, butuh `pip install eth-account` |
| `run.bat` / `run.sh` | launcher Windows / Linux |

## Output

```
[dompet1 0x396a...] SKIP: streak=1 reset=2026-09-12T00:00:00.000Z bal=3010
RINGKASAN: 0 claim | 1 skip | 0 expired | 0 error
```
