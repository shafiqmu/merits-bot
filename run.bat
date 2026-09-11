@echo off
cd /d %~dp0
python claim.py >> claim.log 2>&1
