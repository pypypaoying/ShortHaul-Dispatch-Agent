@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "CONDA_BAT=%CONDA_BAT%"
if "%CONDA_BAT%"=="" set "CONDA_BAT=D:\miniconda3\Scripts\activate.bat"

set "SHORT_HAUL_ENV=%SHORT_HAUL_ENV%"
if "%SHORT_HAUL_ENV%"=="" set "SHORT_HAUL_ENV=shorthaul-agent-exp"

set "SHORT_HAUL_HOST=%SHORT_HAUL_HOST%"
if "%SHORT_HAUL_HOST%"=="" set "SHORT_HAUL_HOST=127.0.0.1"

set "SHORT_HAUL_PORT=%SHORT_HAUL_PORT%"
if "%SHORT_HAUL_PORT%"=="" set "SHORT_HAUL_PORT=8000"

call "%CONDA_BAT%" "%SHORT_HAUL_ENV%"
if errorlevel 1 (
  echo Failed to activate conda environment: %SHORT_HAUL_ENV%
  echo Set SHORT_HAUL_ENV or CONDA_BAT before running this script.
  exit /b 1
)

cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
echo Starting ShortHaul Dispatch Agent at http://%SHORT_HAUL_HOST%:%SHORT_HAUL_PORT%/
python -m uvicorn shorthaul_agent.api:app --host "%SHORT_HAUL_HOST%" --port "%SHORT_HAUL_PORT%"
