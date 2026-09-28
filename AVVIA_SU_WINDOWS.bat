@echo off
cd /d "%~dp0"
py -3 start.py
if errorlevel 1 (
  echo Avvio non riuscito. Installa Python 3 e riprova; oppure usa: python start.py
  pause
)
