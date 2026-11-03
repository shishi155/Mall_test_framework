@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0env-status.ps1" %*
