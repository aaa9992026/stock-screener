@echo off
setlocal
cd /d "%~dp0"
if not exist "StockScreener_Master.xlsx" (
  echo StockScreener_Master.xlsx is missing from this folder.
  pause
  exit /b 1
)
py excel_bridge.py
if errorlevel 1 (
  echo.
  echo Update failed. Check the message above and the Control sheet status.
  pause
)
