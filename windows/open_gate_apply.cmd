@echo off
rem A7S III (firmware 5.01): apply the 3840x2560 open-gate state (three steps; worked on one A7S III, 2026-11-22).
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\s3_apply.py" apply %*
echo.
pause
