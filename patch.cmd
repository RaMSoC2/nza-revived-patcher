@echo off
setlocal
cd /d "%~dp0"
if not exist "input" mkdir "input"
if not exist ".dependencies\python\python.exe" (
  echo Este e o projeto de fontes ou um pacote incompleto.
  echo Use o ZIP portatil completo. Veja o README.md.
  pause
  exit /b 1
)
if exist ".dependencies\source-runtime-mode.json" (
  ".dependencies\python\python.exe" "scripts\source_bootstrap.py" %*
) else (
  ".dependencies\python\python.exe" "scripts\run.py" %*
)
set "nza_exit=%errorlevel%"
if not "%NZA_NO_PAUSE%"=="1" pause
exit /b %nza_exit%
