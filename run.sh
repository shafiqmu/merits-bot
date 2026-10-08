#!/bin/sh
# Termux/Linux: sh run.sh  (log ke claim.log)
# Default: loop 24 jam tanpa batas. Untuk sekali jalan: sh run.sh once
cd "$(dirname "$0")"
if [ "$1" = "once" ]; then
  MERITS_LOOP=1 python3 claim.py >> claim.log 2>&1
else
  python3 claim.py >> claim.log 2>&1
fi
