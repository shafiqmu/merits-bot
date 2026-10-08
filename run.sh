#!/bin/sh
# Termux/Linux: sh run.sh  (log ke claim.log)
# Loop 24 jam:  sh run.sh loop
cd "$(dirname "$0")"
if [ "$1" = "loop" ]; then
  MERITS_LOOP=999999 python3 claim.py >> claim.log 2>&1
else
  python3 claim.py >> claim.log 2>&1
fi
