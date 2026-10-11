@echo off
setlocal
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-client.ps1"
if errorlevel 1 pause
