@echo off
setlocal
cd /d "%~dp0"
echo Installing Python packages for the one-workbook Excel bridge...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Make sure Python 3 is installed and the "py" launcher works.
  pause
  exit /b 1
)
echo.
echo Installation complete.
echo You can now run START_MASTER_EXCEL.bat whenever you want to update the selected stock.
pause
