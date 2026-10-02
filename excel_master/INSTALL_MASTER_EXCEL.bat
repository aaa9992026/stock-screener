@echo off
setlocal
cd /d "%~dp0"
set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE (
  echo Python 3 was not found. Install Python 3 and enable Add Python to PATH.
  pause
  exit /b 1
)
echo Installing packages for the one-workbook Excel updater...
%PYEXE% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check internet access and Python permissions.
  pause
  exit /b 1
)
echo.
echo Installation complete.
echo Open StockScreener_Master.xlsx, set Exchange/Symbol, then run START_MASTER_EXCEL.bat.
pause
