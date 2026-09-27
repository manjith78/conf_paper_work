@echo off
REM run_all.bat -- Windows entry point, mirrors run_all.py exactly (calls it).
REM Usage:
REM   run_all.bat                  full run (downloads dataset if missing)
REM   run_all.bat --skip-download  assumes data\raw\ is already populated
REM   run_all.bat --tests-only     just run the two test suites

setlocal

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [run_all] ERROR: "python" was not found on PATH.
    echo [run_all] Install Python 3.11+ from https://www.python.org/downloads/
    echo [run_all] and make sure "Add python.exe to PATH" is checked during install.
    exit /b 1
)

python "%~dp0run_all.py" %*
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% neq 0 (
    echo.
    echo [run_all] Pipeline stopped with a non-zero exit code. See the output above for which step failed.
) else (
    echo.
    echo [run_all] Done. See paper\tables\ and paper\figures\ for the generated outputs.
)

endlocal
exit /b %EXITCODE%
