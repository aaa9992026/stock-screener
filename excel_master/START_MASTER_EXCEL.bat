@echo off
setlocal
cd /d "%~dp0"
if not exist "StockScreener_Master.xlsx" (
  echo StockScreener_Master.xlsx is missing from this folder.
  pause
  exit /b 1
)
set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE (
  echo Python 3 was not found. Run INSTALL_MASTER_EXCEL.bat after installing Python.
  pause
  exit /b 1
)
attrib -R "StockScreener_Master.xlsx" >nul 2>&1
%PYEXE% excel_bridge.py --workbook "%~dp0StockScreener_Master.xlsx"
if errorlevel 1 (
  echo.
  echo Update failed. Read the message above and the red status box in the Control sheet.
  pause
  exit /b 1
)
echo.
echo Update finished. Data, indicators, backtests and charts were refreshed in the SAME workbook.
pause
