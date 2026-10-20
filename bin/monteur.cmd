@echo off
rem Lanceur MonteurOS pour cmd.exe / PowerShell (Windows).
setlocal
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -m monteur %*
) else (
  py -3 -m monteur %*
)
exit /b %ERRORLEVEL%
