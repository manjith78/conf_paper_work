@echo off
setlocal EnableExtensions EnableDelayedExpansion

title SSM FINAL PROJECT - COMPLETE REPRODUCTION

echo ============================================================
echo   SSM FINAL PROJECT - COMPLETE REPRODUCTION PIPELINE
echo ============================================================
echo.
echo This script will:
echo   1. Check Python
echo   2. Create the virtual environment if needed
echo   3. Install the locked dependencies
echo   4. Run the complete research pipeline
echo   5. Run the complete test suite
echo   6. Check generated results, tables and figures
echo   7. Run ProVerif if it is installed
echo.
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1. CHECK PYTHON
REM ------------------------------------------------------------

echo [1/7] Checking Python...

where python >nul 2>nul

if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py -3"
    ) else (
        echo.
        echo ERROR: Python was not found.
        echo Install Python 3.11 or newer and enable "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% --version

echo.
echo Python found.
echo.

REM ------------------------------------------------------------
REM 2. CREATE VIRTUAL ENVIRONMENT
REM ------------------------------------------------------------

echo [2/7] Checking virtual environment...

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Creating .venv...
    echo.

    %PYTHON_CMD% -m venv .venv

    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )

    echo Virtual environment created.
) else (
    echo Existing .venv found.
)

echo.

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

REM ------------------------------------------------------------
REM 3. INSTALL LOCKED DEPENDENCIES
REM ------------------------------------------------------------

echo [3/7] Installing locked Python dependencies...
echo.

"%VENV_PYTHON%" -m pip install --upgrade pip

if errorlevel 1 (
    echo.
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install -r requirements-lock.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully.
echo.

REM ------------------------------------------------------------
REM 4. RUN COMPLETE PIPELINE
REM ------------------------------------------------------------

echo [4/7] Running COMPLETE research pipeline...
echo.
echo ============================================================
echo   DATASET -> PREPROCESSING -> SSM -> CRYPTO -> EXPERIMENT
echo   -> RESULTS -> TABLES -> FIGURES -> TEST GATE
echo ============================================================
echo.

"%VENV_PYTHON%" run_all.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERROR: MAIN PIPELINE FAILED
    echo ============================================================
    echo.
    echo Check the error messages above.
    pause
    exit /b 1
)

echo.
echo Main pipeline completed successfully.
echo.

REM ------------------------------------------------------------
REM 5. RUN COMPLETE PYTEST SUITE
REM ------------------------------------------------------------

echo [5/7] Running complete pytest suite...
echo.

"%VENV_PYTHON%" -m pytest -q

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERROR: PYTEST SUITE FAILED
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo Pytest suite PASSED.
echo.

REM ------------------------------------------------------------
REM 6. VERIFY EXPECTED OUTPUT FILES
REM ------------------------------------------------------------

echo [6/7] Checking generated output files...
echo.

set "CHECK_FAILED=0"

call :checkfile "results\json\crypto_benchmark.json"
call :checkfile "results\json\ssm_activity_summary.json"
call :checkfile "results\json\sensitivity_analysis.json"
call :checkfile "results\csv\ssm_event_log.csv"
call :checkfile "results\csv\ssm_session_summary.csv"
call :checkfile "paper\tables\table_ii_crypto_benchmark.csv"
call :checkfile "paper\tables\table_iii_ssm_results.csv"
call :checkfile "paper\figures\fig3_compute_cost.png"
call :checkfile "paper\figures\fig4_sensitivity_tmax.png"
call :checkfile "paper\figures\fig5_sensitivity_ath.png"

if "!CHECK_FAILED!"=="1" (
    echo.
    echo ============================================================
    echo ERROR: ONE OR MORE EXPECTED OUTPUT FILES ARE MISSING
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo All expected output files are present.
echo.

REM ------------------------------------------------------------
REM 7. FORMAL VERIFICATION
REM ------------------------------------------------------------

echo [7/7] Checking formal verification...
echo.

where proverif >nul 2>nul

if errorlevel 1 (
    echo WARNING: ProVerif was not found on PATH.
    echo.
    echo Python pipeline and tests are complete.
    echo Formal verification must be run separately after installing
    echo ProVerif.
    echo.
    echo Expected commands:
    echo   cd formal_verification
    echo   proverif -in pitype protocol_model.pv
    echo   proverif -in pitype unbounded_attempt.pv
    echo.
    set "PROVERIF_STATUS=NOT RUN"
) else (
    echo ProVerif found.
    echo.
    echo Running authoritative protocol model...
    echo.

    cd formal_verification

    proverif -in pitype protocol_model.pv > protocol_model_output.txt

    if errorlevel 1 (
        echo.
        echo ERROR: Authoritative ProVerif model failed.
        cd ..
        pause
        exit /b 1
    )

    echo Authoritative ProVerif model completed.
    echo Output saved to:
    echo formal_verification\protocol_model_output.txt
    echo.

    echo Running replicated/unbounded model...
    echo.

    proverif -in pitype unbounded_attempt.pv > unbounded_attempt_output.txt

    if errorlevel 1 (
        echo NOTE: The replicated/unbounded model returned a non-zero
        echo result. This is expected because the model contains the
        echo documented unresolved correspondence result.
        echo.
    )

    cd ..

    set "PROVERIF_STATUS=RUN"
)

REM ------------------------------------------------------------
REM FINAL SUMMARY
REM ------------------------------------------------------------

echo.
echo ============================================================
echo                 REPRODUCTION COMPLETE
echo ============================================================
echo.
echo MAIN PIPELINE       : PASSED
echo PYTEST              : PASSED
echo OUTPUT FILES        : VERIFIED
echo PROVERIF            : %PROVERIF_STATUS%
echo.
echo ============================================================
echo Generated results:
echo ============================================================
echo.
echo   results\json\
echo   results\csv\
echo   paper\tables\
echo   paper\figures\
echo.
echo ============================================================
echo IMPORTANT
echo ============================================================
echo.
echo All numerical results should be taken from the generated
echo result files. Tables and figures are generated from those
echo result files by the project pipeline.
echo.
echo The raw PhysioNet dataset is downloaded and verified
echo automatically if it is not already present.
echo.
echo ============================================================
echo PROJECT REPRODUCTION FINISHED
echo ============================================================
echo.

pause
exit /b 0


REM ============================================================
REM FILE CHECK FUNCTION
REM ============================================================

:checkfile

if exist "%~1" (
    echo [OK] %~1
) else (
    echo [MISSING] %~1
    set "CHECK_FAILED=1"
)

exit /b 0