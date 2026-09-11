#!/bin/sh
# Termux/Linux: sh run.sh  (log ke claim.log)
cd "$(dirname "$0")"
python3 claim.py >> claim.log 2>&1
